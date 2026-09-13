"""Build real distributions and verify manual-driven calls without checkout imports."""

import os
from pathlib import Path
import subprocess
import sys
import sysconfig

import pytest

WORKSPACE = Path(__file__).resolve().parents[2]
PROJECTS = [
    WORKSPACE / "mn-skills" / name
    for name in ("document_reading_skill", "graph_analysis_skill", "pdf_extract_skill")
]
PROJECTS += [WORKSPACE / "mn-agents/prototype_bounded_tool_loop_agent"]
PROJECTS += [WORKSPACE / "mn-python-sdk/packages" / name for name in ("common", "models", "rag")]


@pytest.mark.parametrize("mode", ["source", "wheel"])
def test_isolated_skill_installation(tmp_path, mode):
    target = tmp_path / "installed"
    target.mkdir()
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-deps",
        "--no-build-isolation",
        "--target",
        str(target),
    ]
    for project in PROJECTS:
        if mode == "source":
            command += ["-e"]
        command += [str(project)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    # -S disables site processing and editable .pth injection. Explicit source paths
    # are permitted only for the source test; the wheel process has none.
    paths = [str(target), sysconfig.get_path("purelib")]
    if mode == "source":
        paths = [str(p / "src") for p in PROJECTS] + paths
    script = """
import sys, json, hashlib, io
from pathlib import Path
sys.path[:0] = PATHS
from mn_prototype_bounded_tool_loop_agent.skills import SkillRuntime
from mn_document_reading_skill.search import PassageIndex
from mn_graph_analysis_skill import GraphClient
from mn_pdf_extract_skill import extract_pages_from_pdf
from pypdf import PdfWriter
import mn_document_reading_skill, mn_graph_analysis_skill, mn_pdf_extract_skill
if MODE == 'wheel':
    for module in (mn_document_reading_skill, mn_graph_analysis_skill, mn_pdf_extract_skill):
        assert Path(module.__file__).is_relative_to(TARGET), module.__file__
    for project in PROJECT_ROOTS:
        assert not any(Path(p).resolve() in {Path(project).resolve(), (Path(project) / 'src').resolve()} for p in sys.path)
from mn_sdk_rag.lexical import LexicalKnowledgeIndex
knowledge = LexicalKnowledgeIndex([dict(id='dates', title='Chronology', text='Preserve timestamp context.', source_url='https://example.org/reference', reviewed_at='2026-09-07', jurisdiction='test')])
assert knowledge.retrieve('timestamp')['citations'][0]['id'] == 'dates'
knowledge.close()
text='Cybersecurity review notice.'
index=PassageIndex.build(Path('passages.db'),[dict(source_id='one',text=text,content_sha256=hashlib.sha256(text.encode()).hexdigest(),access_scope='case')],'case')
def pdf(source_id):
    assert source_id=='one'
    stream=io.BytesIO();writer=PdfWriter();writer.add_blank_page(width=72,height=72);writer.write(stream);stream.seek(0)
    return extract_pages_from_pdf(stream)
graph=GraphClient(Path('graph'),binary='/bin/echo')
# Stub only the external engine transport; actual query validation/serialization runs.
graph._run=lambda arguments: json.dumps({'rows':[], 'arguments':arguments})
bindings={('mirrorneuron.document.reading','search'):index.search,
          ('mirrorneuron.document.reading','sources'):index.sources,
          ('mirrorneuron.document.reading','read_source'):index.read_source,
          ('mirrorneuron.document.reading','decode_rot13'):index.decode_rot13,
          ('mirrorneuron.graph.analysis','query'):graph.query,
          ('mirrorneuron.pdf.extract','extract_pages'):pdf}
runtime=SkillRuntime.discover(['mirrorneuron-document-reading-skill','mirrorneuron-graph-analysis-skill','mirrorneuron-pdf-extract-skill'],bindings)
for skill in runtime.list_skills():
    assert runtime.read_skill(skill['id'])['manual']
assert runtime.invoke_skill('mirrorneuron.document.reading','search',{'query':'cybersecurity'})==index.search('cybersecurity')
assert runtime.invoke_skill('mirrorneuron.graph.analysis','query',{'rgql':'MATCH (n) RETURN n LIMIT 5'})==graph.query('MATCH (n) RETURN n LIMIT 5')
assert runtime.invoke_skill('mirrorneuron.pdf.extract','extract_pages',{'source_id':'one'})==pdf('one')
for op, args in [('sources', {}), ('read_source', {'source_id':'one'}), ('decode_rot13', {'source_id':'one'})]:
    assert runtime.invoke_skill('mirrorneuron.document.reading', op, args) == getattr(index, op)(**args)
print('manual discovery and dual-use operations passed')
"""
    prefix = f"PATHS={paths!r}\nMODE={mode!r}\nTARGET={str(target)!r}\nPROJECT_ROOTS={[str(p) for p in PROJECTS]!r}\n"
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", prefix + script],
        cwd=tmp_path,
        env=dict(os.environ, MN_SKILL_LOG_PATH=str(tmp_path / "skill.log")),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
