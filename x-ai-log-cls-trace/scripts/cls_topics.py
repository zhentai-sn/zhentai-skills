#!/usr/bin/env python3
"""列出腾讯云 CLS 日志主题（Topic），按关键词过滤，拿到检索用的 TopicId。

用法：
    python cls_topics.py [关键词]

- 关键词缺省列全部；带关键词时按 TopicName 子串（大小写不敏感）过滤。
- 读环境变量 TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY / TENCENTCLOUD_REGION。
- 自动翻页（DescribeTopics 单页 Limit 上限 100）。

输出每行：<TopicId> | <TopicName>
检索时把 TopicId 喂给 cls_search.py。注意 TopicId 有时是 UUID，有时是
形如 `<user-center-container>` 的可读串——两者都直接用。
"""
from __future__ import annotations

import os
import sys

from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.cls.v20201016 import cls_client, models


def build_client() -> cls_client.ClsClient:
    sid = os.getenv("TENCENTCLOUD_SECRET_ID")
    skey = os.getenv("TENCENTCLOUD_SECRET_KEY")
    region = os.getenv("TENCENTCLOUD_REGION")
    if not sid or not skey:
        raise SystemExit("缺 TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY")
    if not region:
        raise SystemExit("缺 TENCENTCLOUD_REGION（如 ap-guangzhou）")
    cred = credential.Credential(sid, skey)
    hp = HttpProfile()
    hp.endpoint = "cls.tencentcloudapi.com"
    cp = ClientProfile()
    cp.httpProfile = hp
    return cls_client.ClsClient(cred, region, cp)


def list_topics(client: cls_client.ClsClient) -> list[dict]:
    import json

    all_topics: list[dict] = []
    offset = 0
    while True:
        req = models.DescribeTopicsRequest()
        req.Limit = 100  # 上限 100，传 200 会报 InvalidParameterValue
        req.Offset = offset
        data = json.loads(client.DescribeTopics(req).to_json_string())
        topics = data.get("Topics", []) or []
        all_topics.extend(topics)
        if len(all_topics) >= data.get("TotalCount", 0) or not topics:
            break
        offset += 100
    return all_topics


def main() -> None:
    keyword = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
    topics = list_topics(build_client())
    matched = [
        t
        for t in topics
        if not keyword or keyword in (t.get("TopicName", "") or "").lower()
    ]
    print(f"# 共 {len(topics)} 个主题，匹配 {len(matched)} 个", file=sys.stderr)
    for t in matched:
        print(f"{t.get('TopicId')} | {t.get('TopicName')}")


if __name__ == "__main__":
    main()
