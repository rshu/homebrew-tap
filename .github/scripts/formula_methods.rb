  def install
    wheelhouse = buildpath/"wheelhouse"
    wheelhouse.mkpath
    resources.each do |resource|
      resource.stage do
        wheelhouse.install Dir["*.whl"]
      end
    end
    venv = virtualenv_create(libexec, "python3.14", system_site_packages: false)
    ENV["PIP_NO_INDEX"] = "1"
    ENV["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    venv.pip_install wheelhouse.glob("*.whl"), build_isolation: false
    venv.pip_install_and_link buildpath/"agent_trajviz-#{version}-py3-none-any.whl", build_isolation: false
  end

  def caveats
    <<~EOS
      Start the dashboard with:
        agent-trajviz
      Then open http://127.0.0.1:7860.

      This tap installs the full dashboard in an isolated Python environment.
      Model connections and API keys are configured in the dashboard's Settings.
    EOS
  end

  test do
    %w[agent-trajviz agent-trajviz-converge agent-trajviz-collect agent-trajviz-label].each do |command|
      assert_match version.to_s, shell_output("#{bin}/#{command} --version")
      assert_match "usage:", shell_output("#{bin}/#{command} --help")
    end

    (testpath/"session.jsonl").write <<~JSONL
      {"type":"user","sessionId":"brew-test","message":{"role":"user","content":"Inspect the failing test"}}
      {"type":"assistant","sessionId":"brew-test","message":{"role":"assistant","model":"test-model","content":[{"type":"text","text":"Run the test"},{"type":"tool_use","id":"tool-1","name":"Bash","input":{"command":"pytest -q"}}],"usage":{"input_tokens":10,"output_tokens":5}}}
      {"type":"user","sessionId":"brew-test","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"tool-1","content":"3 passed"}]}}
    JSONL
    system bin/"agent-trajviz", "--json", testpath/"session.jsonl", "-o", testpath/"export"
    system bin/"agent-trajviz", "--report", testpath/"session.jsonl", "-o", testpath/"report.html", "--inline-plotly"
    assert_path_exists testpath/"export/trajectory.json"
    assert_match "<html", (testpath/"report.html").read

    (testpath/"smoke.py").write <<~PYTHON
      import json
      import os
      import urllib.request

      os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"
      import agent_trajviz as tv
      from agent_trajviz.dashboard import insight_app, converge_app

      run = tv.load("export/trajectory.json")
      assert run.metrics["tokens"]["total"] == 15, run.metrics["tokens"]
      assert run.view("tool_usage").data["tools"][0]["calls"] == 1
      assert all(json.loads(view.to_json()) for view in run.views().values())
      for factory in (insight_app, converge_app):
          app = factory()
          try:
              _, url, _ = app.launch(server_name="127.0.0.1", server_port=#{free_port},
                                     prevent_thread_lock=True, quiet=True, inbrowser=False)
              with urllib.request.urlopen(url, timeout=20) as response:
                  assert response.status == 200
                  assert b"<html" in response.read()
          finally:
              app.close()
    PYTHON
    system libexec/"bin/python", testpath/"smoke.py"
    system "python3.14", "-m", "pip", "--python=#{libexec}/bin/python", "check"
  end
end
