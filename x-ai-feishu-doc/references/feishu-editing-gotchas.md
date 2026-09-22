# 飞书 DocxXML 与 lark-cli 实操坑

改飞书长文档时踩过的坑与安全改法。命令语义见 `lark-doc`，这里只记**会静默出错**的地方。

## 命令形态

- 所有值走 flag，**不支持位置参数**：`--doc <URL>` 而不是直接跟 URL
- `--content` 的 `@file` **只认工作目录内的相对路径**；scratchpad 里的文件要用管道 + `--content -`
- 文档开头插入用 `--block-id 0`（document start 哨兵），文末用 `-1`

## block 定位

| 现象 | 原因 | 改法 |
| --- | --- | --- |
| `an intermediate sibling has no block ID` | 飞书的 `<ul>` / `<ol>` 容器没有 block id，只有 `<li>` 有 | 先 `block_delete` 掉 li 区间，再对剩下的兄弟块做 `block_replace` |
| `must be sibling blocks under the same parent` | 起止块不在同一层 | 重新 fetch 确认层级，分段处理 |
| `start_block_id not found` | 替换过标题块，**block id 已经换了** | 每次结构性改动后重新 fetch 取新 id |

**范围替换的安全姿势**：优先只替换单个块（把新增内容一起塞进那一个 `block_replace` 的 content），避免跨越 id-less 的列表容器。

## XML 写法

- **行内 code 不支持**。`<code>` 只能在 `<pre>` 里。行内标识符用 `<span background-color="light-gray">xxx</span>`
- **代码块不能嵌在列表项内**，会「Nesting still failed after degrade」，拍平成顶层块
- `<callout>` 只接受 `p` / `ol` / `ul` / `checkbox` / 行内标签，**不能放 table、img、pre、hr、grid、whiteboard**
- 标题层级不能跳级，`h1` 后不能直接 `h3`
- 转义只转文本内容：`<` → `&lt;`、`>` → `&gt;`、`&` → `&amp;`
- 写之前本地校验一遍：`python3 -c "import xml.etree.ElementTree as ET; ET.fromstring('<root>'+open(f).read()+'</root>')"`

## 表格

- **禁止用 `--doc-format markdown` 整表 `block_replace`**——会静默抹掉所有单元格底色、列宽和字重。用户会手动调这些
- 改单元格文字：`str_replace`（注意 pattern 要在全文唯一）
- 改表格结构：`--detail full` 拉 XML → 改 XML → `block_replace`
- 表头用 `background-color="light-gray"`；彩色单元格只用于表达状态或分类
- 重建带 @成员的表时，`<cite type="user" user-id="ou_xxx"></cite>` 要原样带上 `user-id`，重建后 fetch 验证人还在
- 合并单元格用 `rowspan` / `colspan`，被合并的格不再写

## 画板

- SVG **不支持 `<marker>`**，箭头用 `<polygon>` + `<line>` 画
- SVG **不能含 `<!-- -->` 注释**，否则解析降级、源码会漏进正文
- 更新已有画板必须复用原 token，不要新建空白画板
- 导出看内容：`whiteboard +export --whiteboard-token <T> --output-type raw`，再按 x/y 排序读文字节点

## 版本历史

```bash
lark-cli docs +history-list --doc <URL> --as user --page-size 20
lark-cli docs +fetch --doc <URL> --scope section --start-block-id <锚点> \
  --detail full --revision-id <N>
```

- `--detail full` 才带样式；`--detail with-ids` 会**省略 `<b>` 等样式标记**，别拿它判断字重
- 取回的 XML 要 `re.sub(r'\s+id="[^"]*"','',xml)` 去掉旧 block id 再写回
- 整篇 `history-revert` 会回滚全文，逐节还原不要用它

## 验证

每条命令单独执行并检查 `ok` 与 `result`：

```bash
... | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['ok'], d.get('data',{}).get('result'), d.get('error',''))"
```

写完通读渲染结果（`--doc-format markdown`），重点看：callout 有没有降级、嵌套列表有没有塌、交叉引用还成不成立。
