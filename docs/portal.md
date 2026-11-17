# 本地来源行为

摊位申报目录列出稳定的 `data-key` 和详情路径；详情需由浏览器导航读取，`摊位类别`选择改变当前页面状态，`上传预览`和`确认草稿`是分步出现的可见内容。换类别后原有附件预览可能留在草稿。详情接口是浏览器页面，不是业务 API；运行时只允许访问环回来源。

详情页增量约定（不改动既有元素 id 与文案）：

- `#material-requirement` 显示当前类别对应的所需材料，类别变化时同步更新。
- 换类别会清空附件输入与 `#upload-digest` 摘要并递增草稿版本，旧材料不再附在当前类别申请上。
- `#upload-digest` 是附件内容的 SHA-256；同名文件内容不同则摘要不同，材料身份以摘要而非文件名判断。
- 无已核对材料点击 `#confirm` 时，`#validation-error` 显示校验错误并把焦点移回 `#attachment`；确认页按钮只生成会话内文案，不发起任何网络写请求。
- 草稿写入 `sessionStorage`（键 `stall-draft:<data-key>`）；离开页面或 reload 后同会话可恢复，但附件文件不恢复，必须重新上传核对；新会话无草稿。

`fixtures/portal.json` 提供合成业务资料，不包含真实个人数据。`records.save_catalog` 覆盖同一目录身份；`records.save_detail_entries` 以业务键追加入口访问，不把入口访问等同于资格、授权、可预约或正式提交。测试均只访问本地环回页面。`app.drill.run_draft_drill` 演练完整草稿流并拦截一切 POST/PUT/PATCH/DELETE；`app.handoff` 只把观察到的草稿事实整理为人工复核记录，结论 `not_performed` 不代表资格或提交。
