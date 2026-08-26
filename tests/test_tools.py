from pathlib import Path

from codereview_agent.tools import collect_source_files, run_python_static_checks


def test_collect_source_files_and_detect_bare_except(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("try:\n    pass\nexcept:\n    pass\n", encoding="utf-8")

    files = collect_source_files(tmp_path)
    findings = run_python_static_checks(files)

    assert [item.path for item in files] == ["sample.py"]
    assert findings[0]["title"] == "裸 except 捕获了所有异常"


def test_static_checks_detect_security_and_mutable_defaults(tmp_path: Path) -> None:
    source = tmp_path / "unsafe.py"
    source.write_text(
        "import subprocess\n"
        "def run(items=[]):\n"
        "    eval(items[0])\n"
        "    subprocess.run(items[0], shell=True)\n",
        encoding="utf-8",
    )

    findings = run_python_static_checks(collect_source_files(tmp_path))
    titles = {item["title"] for item in findings}

    assert titles == {
        "函数使用了可变默认参数",
        "动态代码执行存在安全风险",
        "子进程调用使用了 shell=True",
    }
