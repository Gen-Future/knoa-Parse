# 开发前测试需求：M3-D PDF 渲染器边界与资源预算

创建日期：2026-11-02；状态：实现前定义。范围：PDF 原件字节、页规格、受控 Renderer 注入和栅格输出预算；不选择具体渲染库，不增加依赖，不调用 OCR/外部服务，不接入 API/worker。

## 目标与边界

渲染编排层只接收已经固定的 PDF Source 字节和页规格，不接收任意文件路径、不自行下载 URL。它在调用 Renderer 前核对 Source SHA/大小、PDF media type、页集合和页数预算；Renderer 必须声明接受的渲染预算并返回 `RasterPageInput`。返回值再经过 M3-C 的来源、整页比例、旋转和 artifact 校验。

本阶段的预算是编排层检查，不是完整 OS 沙箱或强制中断：Renderer 如果在调用内部失控，必须由后续 worker 子进程/平台边界处理。当前不实现 PDF 渲染库，合成 Renderer 只产生固定字节。

## 验收用例

- [ ] M3D-01 / P0：合法 PDF Source 字节只传给 Renderer 一次；Renderer 请求包含页规格/预算，不含路径、URL 或凭据；输出进入 M3-C。
- [ ] M3D-02 / P0：源 media type、SHA、size 不一致时在 Renderer 调用前拒绝；原生 ParseResult 不变。
- [ ] M3D-03 / P0：页数、请求页集合、重复页和未知页在调用前拒绝；所有页先预检，不返回部分结果。
- [ ] M3D-04 / P0：单页输出字节、总输出字节、像素数超过预算时拒绝；不发布之前已返回的部分栅格。
- [ ] M3D-05 / P0：Renderer 返回缺页、多页、错误页、错误媒体、错误 aspect ratio、artifact 冲突时由 M3-C 拒绝。
- [ ] M3D-06 / P1：页规格乱序时 Renderer 看到明确排序或显式约定，最终 `PreparedPage` 按页号排序；不串页字节。
- [ ] M3D-07 / P1：Renderer 异常不会被改写成成功；公开错误不包含 PDF 字节、路径或敏感内容。
- [ ] M3D-08 / P0：预算仅作为受控参数传递，文档明确同步 Renderer 未被强制超时；后续 worker 边界另行处理。
- [ ] M3D-09 / P0：M3-A 使用 Renderer 输出时，source/page/artifact/context 语义保持；原生结果不被修改。
- [ ] M3D-10 / P0：专项、M3 编排、完整回归、文档/契约检查和依赖审计通过；不新增渲染库或能力清单项目。

自动测试使用固定合成字节，仅证明编排和预算。真实 PDF 渲染器选择、许可证、字体、裁切、旋转、质量和性能进入开发后 TODO。开发后记录：[M3-D after](2026-11-02-m3d-renderer-boundary-after.md)。
