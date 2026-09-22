from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import (
    TencentCloudSDKException,
)
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.cls.v20201016 import cls_client, models


logger = logging.getLogger(__name__)


def _build_client(
    secret_id: Optional[str] = None,
    secret_key: Optional[str] = None,
    region: Optional[str] = None,
) -> cls_client.ClsClient:
    """
    构建 CLS 客户端实例。
    """
    secret_id_value = secret_id or os.getenv("TENCENTCLOUD_SECRET_ID")
    secret_key_value = secret_key or os.getenv("TENCENTCLOUD_SECRET_KEY")
    region_value = region or os.getenv("TENCENTCLOUD_REGION")

    if not secret_id_value or not secret_key_value:
        raise ValueError("腾讯云鉴权信息缺失：需要 SecretId 与 SecretKey。")
    if not region_value:
        raise ValueError("腾讯云区域配置缺失：需要 region。")

    cred = credential.Credential(secret_id_value, secret_key_value)
    http_profile = HttpProfile()
    http_profile.endpoint = "cls.tencentcloudapi.com"

    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile

    logger.debug("初始化 CLS 客户端，region=%s", region_value)
    return cls_client.ClsClient(cred, region_value, client_profile)


def _search_single_trace(
    client: cls_client.ClsClient,
    topic_ids: Sequence[str],
    query: str,
    start_time: int,
    end_time: int,
    limit_per_topic: int,
    trace_field: str,
) -> List[Dict[str, Any]]:
    """
    使用指定查询条件在多个topic中检索日志。
    """
    all_logs: List[Dict[str, Any]] = []

    for topic_id in topic_ids:
        logger.info("检索日志，topic_id=%s, query=%s", topic_id, query)
        req = models.SearchLogRequest()
        req.TopicId = topic_id
        req.Query = query
        req.From = start_time
        req.To = end_time
        req.Limit = limit_per_topic
        req.Sort = "asc"

        try:
            resp = client.SearchLog(req)
        except TencentCloudSDKException as exc:
            logger.error("调用 CLS SearchLog 失败，topic_id=%s, error=%s", topic_id, exc)
            continue

        if not getattr(resp, "Results", None):
            logger.info("topic_id=%s 未检索到日志。", topic_id)
            continue

        topic_logs = _normalize_search_results(resp.Results, topic_id)
        all_logs.extend(topic_logs)

    return all_logs


def search_logs_by_trace(
    trace_id: str,
    topic_ids: Sequence[str],
    start_time: int,
    end_time: int,
    *,
    limit_per_topic: int = 200,
    secret_id: Optional[str] = None,
    secret_key: Optional[str] = None,
    region: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    按 TraceID 调用腾讯云 CLS SearchLog 接口检索多主题日志。
    """
    if not trace_id:
        raise ValueError("trace_id 不能为空。")
    if not topic_ids:
        raise ValueError("topic_ids 不能为空。")
    if start_time >= end_time:
        raise ValueError("start_time 必须早于 end_time。")

    client = _build_client(secret_id=secret_id, secret_key=secret_key, region=region)

    all_logs: List[Dict[str, Any]] = []
    # 尝试多种可能的trace字段名
    for trace_field in ["traceId", "trace_id", "trace-id", "TraceId"]:
        query = f'{trace_field}:"{trace_id}"'
        topic_logs = _search_single_trace(
            client, topic_ids, query, start_time, end_time, limit_per_topic, trace_field
        )
        if topic_logs:
            logger.info("使用字段名 %s 成功检索到 %d 条日志", trace_field, len(topic_logs))
            all_logs.extend(topic_logs)
            break
    else:
        # 如果索引字段搜索失败，尝试全文搜索
        logger.info("索引字段搜索失败，尝试全文搜索...")
        query = f'"{trace_id}"'
        topic_logs = _search_single_trace(
            client, topic_ids, query, start_time, end_time, limit_per_topic, "全文"
        )
        if topic_logs:
            logger.info("全文搜索成功检索到 %d 条日志", len(topic_logs))
            all_logs.extend(topic_logs)
        else:
            logger.warning("未能在任何trace字段名下检索到日志")

    all_logs.sort(key=lambda item: item.get("timestamp", 0))
    logger.info("完成 TraceID=%s 日志检索，汇总条数=%d", trace_id, len(all_logs))
    return all_logs


def _normalize_search_results(
    results: Sequence[Any],
    topic_id: str,
) -> List[Dict[str, Any]]:
    """
    规范化 CLS SearchLog 返回结果，转换为通用字典结构。
    """
    normalized: List[Dict[str, Any]] = []

    for item in results:
        log_obj: Dict[str, Any] = {
            "topic_id": topic_id,
            "timestamp": getattr(item, "Time", 0),
        }

        # 尝试多种可能的日志内容字段
        raw_content = (
            getattr(item, "Log", None)
            or getattr(item, "Content", None)
            or getattr(item, "LogJson", None)
            or getattr(item, "Message", None)
        )

        if raw_content is None:
            # 如果没有找到日志内容，尝试获取整个item的属性
            log_obj["raw_message"] = str(item)
        elif isinstance(raw_content, str):
            try:
                parsed = json.loads(raw_content)
                if isinstance(parsed, dict):
                    log_obj.update(parsed)
                else:
                    log_obj["raw_message"] = raw_content
            except json.JSONDecodeError:
                log_obj["raw_message"] = raw_content
        elif isinstance(raw_content, dict):
            log_obj.update(raw_content)
        else:
            log_obj["raw_message"] = str(raw_content)

        normalized.append(log_obj)

    return normalized


def _parse_time_range(args: Sequence[str]) -> Tuple[int, int]:
    """
    从命令行参数中解析时间范围（Unix 时间戳，秒）。
    """
    if len(args) != 2:
        raise ValueError("时间范围参数格式错误，应为：start_ts end_ts。")

    start_time = int(args[0])
    end_time = int(args[1])

    if start_time >= end_time:
        raise ValueError("start_ts 必须小于 end_ts。")

    return start_time, end_time


def main() -> None:
    """
    命令行入口：按 TraceID 从 CLS 检索日志，并输出 JSON。
    """
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    if len(sys.argv) != 5:
        raise SystemExit(
            "用法：python cls_search.py <trace_id> <topic_ids> <start_ts> <end_ts>\n"
            "示例：python cls_search.py 123abc topicA,topicB 1719830400 1719834000"
        )

    trace_id = sys.argv[1]
    topic_ids_arg = sys.argv[2]
    start_time, end_time = _parse_time_range(sys.argv[3:5])

    topic_ids = [topic.strip() for topic in topic_ids_arg.split(",") if topic.strip()]
    logs = search_logs_by_trace(
        trace_id=trace_id,
        topic_ids=topic_ids,
        start_time=start_time,
        end_time=end_time,
    )

    print(json.dumps(logs, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()