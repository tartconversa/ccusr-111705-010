# 市集摊位申报的浏览器草稿移交

这是摊位申报资料的本地演练门户与目录采集器。演练数据仅在环回地址提供，不会操作真实用户、订单或商户。当前 `app.capture.read_catalog` 读取目录；`app.capture.read_detail_entry` 走卡片到详情并接收可选业务选择，`app.domain.interpret_entry` 确认业务身份，`app.records.save_detail_entries` 追加详情入口收据。页面有分步交互，但完整核对、异常恢复及业务结论仍待实现。

站点约定见 `docs/portal.md`；测试时从本地任意空闲端口启动演练站点。安装锁定依赖并准备 Chromium 后：

- `python -m unittest discover -s tests -v`：运行基线浏览器测试。
- `python -m compileall -q app tests`：检查代码。
- `python -m app.site`：启动本地演练站点。
- `python -m app.cli`：另一个终端观察目录输出。

两个终端命令用于人工演示，自动测试不依赖固定端口。
