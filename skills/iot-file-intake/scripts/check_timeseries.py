#!/usr/bin/env python3
"""时序数据质检：CSV → 四维质量指标（零第三方依赖）

用法：
    python check_timeseries.py data.csv [--time-col 时间] [--value-col 数值] [--device-col 设备ID] \
        [--interval 300] [--late-threshold 5] [--recv-col 接收时间] [--min -40] [--max 85] [--out report.json]

输出指标：行数、设备数、完整率、及时率（有接收时间时）、异常率（量程/3σ）、卡值、重复、乱序
"""

import argparse
import csv
import json
import statistics
import sys
from datetime import datetime


def parse_time(v):
    v = str(v).strip()
    if not v:
        return None
    if v.replace(".", "", 1).isdigit():
        try:
            return datetime.fromtimestamp(float(v))
        except (ValueError, OSError):
            return None
    v2 = v.replace("/", "-").replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(v2, fmt)
        except ValueError:
            continue
    return None


def to_float(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def find_col(header, candidates, fallback_idx=None):
    norm = lambda s: "".join(str(s).split()).lower()
    for c in candidates:
        for i, h in enumerate(header):
            if norm(c) == norm(h) or norm(c) in norm(h):
                return i
    return fallback_idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--time-col", default=None)
    ap.add_argument("--value-col", default=None)
    ap.add_argument("--device-col", default=None)
    ap.add_argument("--recv-col", default=None, help="平台接收时间列，用于计算及时率")
    ap.add_argument("--interval", type=float, default=None, help="预期上报周期（秒）")
    ap.add_argument("--late-threshold", type=float, default=5.0, help="延迟阈值（秒），默认 5")
    ap.add_argument("--min", type=float, default=None)
    ap.add_argument("--max", type=float, default=None)
    ap.add_argument("--stuck-run", type=int, default=10, help="连续相同值判定卡值的长度")
    ap.add_argument("--out", default="quality_report.json")
    args = ap.parse_args()

    with open(args.file, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("数据为空")
        return 1
    header = list(rows[0].keys())

    t_i = find_col(header, [args.time_col] if args.time_col else ["时间", "timestamp", "time", "采集时间"])
    v_i = find_col(header, [args.value_col] if args.value_col else ["数值", "value", "读数", "metric_value"])
    d_i = find_col(header, [args.device_col] if args.device_col else ["设备id", "device_id", "deviceid", "设备"])
    r_i = find_col(header, [args.recv_col] if args.recv_col else ["接收时间", "recv_time", "server_time"])

    t_key = header[t_i] if t_i is not None else None
    v_key = header[v_i] if v_i is not None else None
    d_key = header[d_i] if d_i is not None else None
    r_key = header[r_i] if r_i is not None else None
    if not v_key:
        print("未找到数值列，请用 --value-col 指定")
        return 1

    by_dev = {}
    for r in rows:
        dev = (r.get(d_key) or "ALL").strip() if d_key else "ALL"
        by_dev.setdefault(dev, []).append(r)

    results = {}
    total_expected = total_actual = 0
    for dev, recs in by_dev.items():
        times = [parse_time(r.get(t_key)) for r in recs] if t_key else []
        times = [t for t in times if t]
        times.sort()
        actual = len(recs)
        expected = None
        if args.interval and len(times) >= 2:
            span = (times[-1] - times[0]).total_seconds()
            expected = int(span / args.interval) + 1
        latencies = []
        if r_key and t_key:
            for r in recs:
                t1, t2 = parse_time(r.get(t_key)), parse_time(r.get(r_key))
                if t1 and t2:
                    latencies.append((t2 - t1).total_seconds())
        values = [v for v in (to_float(r.get(v_key)) for r in recs) if v is not None]

        anomalies = 0
        range_hits = 0
        sigma_hits = 0
        if values:
            if args.min is not None or args.max is not None:
                for v in values:
                    if (args.min is not None and v < args.min) or (args.max is not None and v > args.max):
                        range_hits += 1
            if len(values) >= 30:
                mu = statistics.fmean(values)
                sd = statistics.pstdev(values)
                if sd > 0:
                    sigma_hits = sum(1 for v in values if abs(v - mu) > 3 * sd)
            anomalies = max(range_hits, sigma_hits)

        # 卡值：按时间排序后连续相同值
        stuck = 0
        if len(values) >= args.stuck_run:
            run = 1
            for i in range(1, len(values)):
                if values[i] == values[i - 1]:
                    run += 1
                    if run == args.stuck_run:
                        stuck += 1
                else:
                    run = 1

        dup = actual - len({(r.get(t_key), r.get(v_key)) for r in recs}) if t_key else 0
        disorder = sum(1 for i in range(1, len(times)) if times[i] < times[i - 1])

        total_actual += actual
        if expected:
            total_expected += expected

        results[dev] = {
            "rows": actual,
            "expectedRows": expected,
            "completeness": round(actual / expected * 100, 2) if expected else None,
            "timeliness": round(sum(1 for x in latencies if x <= args.late_threshold) / len(latencies) * 100, 2) if latencies else None,
            "p95LatencySec": round(sorted(latencies)[int(len(latencies) * 0.95) - 1], 1) if latencies else None,
            "valueCount": len(values),
            "anomalyCount": anomalies,
            "anomalyRate": round(anomalies / len(values) * 100, 2) if values else None,
            "outOfRange": range_hits,
            "sigmaOutlier": sigma_hits,
            "stuckRuns": stuck,
            "duplicates": dup,
            "disorder": disorder,
        }

    overall = {
        "completeness": round(total_actual / total_expected * 100, 2) if total_expected else None,
    }
    report = {"source": args.file, "params": vars(args) | {"file": None}, "overall": overall,
              "devices": results}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"设备数：{len(results)}；总行数：{total_actual}")
    if overall["completeness"] is not None:
        print(f"整体完整率：{overall['completeness']}%（按预期周期 {args.interval}s 计算）")
    print("\n| 设备 | 行数 | 完整率 | 及时率 | P95延迟(s) | 异常率 | 卡值 | 重复 | 乱序 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for dev, r in list(results.items())[:30]:
        print(f"| {dev} | {r['rows']} | {r['completeness'] if r['completeness'] is not None else '-'} | "
              f"{r['timeliness'] if r['timeliness'] is not None else '-'} | {r['p95LatencySec'] or '-'} | "
              f"{r['anomalyRate'] if r['anomalyRate'] is not None else '-'} | {r['stuckRuns']} | "
              f"{r['duplicates']} | {r['disorder']} |")
    print(f"\n明细已写入 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
