# 市集摊位申报的浏览器草稿移交

这是摊位申报资料的本地演练门户与目录采集器。演练数据仅在环回地址提供，不会操作真实用户、订单或商户。当前 `app.capture.read_catalog` 用 Playwright/Chromium 访问目录卡片，`app.site` 提供目录与可交互详情，`app.domain` 解析既有卡片字段，`app.records` 只保存目录收据；详情选择、上传预览和确认草稿尚未纳入采集。

站点约定见 `docs/portal.md`；测试时从本地任意空闲端口启动演练站点。安装锁定依赖并准备 Chromium 后：

- `python -m unittest discover -s tests -v`：运行基线浏览器测试。
- `python -m compileall -q app tests`：检查代码。
- `python -m app.site`：启动本地演练站点。
- `python -m app.cli`：另一个终端观察目录输出。

两个终端命令用于人工演示，自动测试不依赖固定端口。
