from evalscope import TaskConfig, run_task


config = TaskConfig(
    model="nanbeige4.2:3b-q6",
    api_url="http://127.0.0.1:11435/v1",
    api_key="ollama",
    eval_type="openai_api",
    datasets=["gsm8k"],
    dataset_dir="./eval-data",
    dataset_hub="modelscope",
    limit=3,
    generation_config={
        "temperature": 0,
        "max_tokens": 1024,
    },
    work_dir="./eval-results",
    no_timestamp=True,
    collect_perf=True,
    debug=True,
)

run_task(task_cfg=config)
