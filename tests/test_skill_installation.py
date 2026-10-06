"""Build real distributions and verify manual-driven calls without checkout imports."""

import os
import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest

WORKSPACE = Path(__file__).resolve().parents[2]
PROJECTS = [
    WORKSPACE / "mn-skills" / name
    for name in ("graph_analysis_skill", "web_browser_skill")
]
PROJECTS += [WORKSPACE / "mn-agents/prototype_bounded_tool_loop_agent"]
PROJECTS += [WORKSPACE / "mn-python-sdk/packages" / name for name in ("common",)]


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
import sys, json
from pathlib import Path
sys.path[:0] = PATHS
from mn_prototype_bounded_tool_loop_agent.skills import SkillRuntime
from mn_graph_analysis_skill import GraphClient
from mn_web_browser_skill import browse, WebBrowserConfig
import mn_graph_analysis_skill, mn_web_browser_skill
if MODE == 'wheel':
    for module in (mn_graph_analysis_skill, mn_web_browser_skill):
        assert Path(module.__file__).is_relative_to(TARGET), module.__file__
    for project in PROJECT_ROOTS:
        assert not any(Path(p).resolve() in {Path(project).resolve(), (Path(project) / 'src').resolve()} for p in sys.path)
graph=GraphClient(Path('graph'),binary='/bin/echo')
# Stub external transports; public validation, extraction and serialization run.
graph._run=lambda arguments: json.dumps({'rows':[], 'arguments':arguments})
from mn_web_browser_skill import runtime as browser_setup
preparations=[]
def setup(request):
    assert request == {'version':1,'allow_install':True}
    preparations.append(request)
    return {'version':1,'status':'ready'}
browser_setup.prepare_runtime=setup
config=WebBrowserConfig(respect_robots=False,per_host_delay_seconds=0,min_text_chars=20)
html='<html><body><article><h1>Local evidence</h1><p>Public fixture evidence is read locally for this installation test.</p></article></body></html>'
def read(url,depth='fast'):
    return browse(url,config,depth=depth,http_fetcher=lambda url,config,timeout:{'status':'ok','html':html,'url':url,'http_status':200})
bindings={('mirrorneuron.web.browser','browse'):read,
          ('mirrorneuron.graph.analysis','query'):graph.query}
runtime=SkillRuntime.discover(['mirrorneuron-web-browser-skill','mirrorneuron-graph-analysis-skill'],bindings)
assert len(preparations)==1
for skill in runtime.list_skills():
    assert runtime.read_skill(skill['id'])['manual']
page=runtime.invoke_skill('mirrorneuron.web.browser','browse',{'url':'https://example.test','depth':'fast'})
assert page['status']=='ok' and 'Public fixture evidence' in page['text']
assert read('https://example.test')['text']==page['text']
assert runtime.invoke_skill('mirrorneuron.graph.analysis','query',{'rgql':'MATCH (n) RETURN n LIMIT 5'})==graph.query('MATCH (n) RETURN n LIMIT 5')
assert len(preparations)==1
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
