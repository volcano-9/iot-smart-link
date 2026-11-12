#!/usr/bin/env python3
"""点表解析：Excel/CSV 点表 → 物模型测点表（零第三方依赖）

用法：
    python parse_pointtable.py <pointtable.xlsx|csv> [--out points.json] [--product-key PK] [--sheet N]

输出：
    - 标准测点 JSON（measurementPoints）
    - Markdown 测点表（便于直接贴进报告）
    - warnings：未识别的列、疑似缺列、空值统计
"""

import argparse
import csv
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# 列名别名（按优先级顺序匹配，先长后短）
ALIASES = {
    "tag": ["测点编码", "测点编号", "点位编号", "点位号", "点号", "测点代码", "tag", "pointid", "point_no", "pointno", "id", "测点"],
    "property": ["物模型属性", "属性标识", "属性名", "属性", "identifier", "prop"],
    "name": ["测点名称", "点位名称", "点描述", "测点描述", "描述", "名称", "name", "desc"],
    "dataType": ["数据类型", "寄存器类型", "类型", "datatype", "data_type", "type"],
    "channel": ["寄存器地址", "采集通道", "通道地址", "地址码", "寄存器", "地址", "channel", "address", "addr", "reg"],
    "slave": ["从站地址", "从站号", "站号", "slave"],
    "funcCode": ["功能码", "功能号", "function", "fc"],
    "byteOrder": ["字节序", "字序", "byteorder", "byte_order", "endian"],
    "scale": ["缩放系数", "换算系数", "系数", "倍率", "比例", "scale", "ratio", "factor"],
    "offset": ["偏移量", "偏移值", "偏移", "offset"],
    "unit": ["工程单位", "单位", "unit"],
    "min": ["量程下限", "最小值", "下限", "min"],
    "max": ["量程上限", "最大值", "上限", "max"],
    "range": ["量程", "range"],
    "sampleInterval": ["采集周期", "采样周期", "上报周期", "周期", "interval", "sampling"],
    "deadband": ["变化阈值", "死区", "deadband"],
    "quality": ["质量码", "quality", "qos_code"],
    "location": ["安装位置", "位置", "location", "pos"],
    "alarm": ["告警阈值", "报警阈值", "阈值", "alarm", "threshold"],
}


def norm(s):
    if s is None:
        return ""
    return re.sub(r"[\s\u3000()（）:：\-_/]", "", str(s)).lower()


def build_header_map(header):
    """返回 {字段: 列下标}，按别名优先级独占匹配，避免'地址'抢占'从站地址'"""
    out = {}
    used = set()
    for field, alias_list in ALIASES.items():
        for alias in sorted(alias_list, key=len, reverse=True):
            a = norm(alias)
            for idx, h in enumerate(header):
                if idx in used:
                    continue
                hn = norm(h)
                if not hn:
                    continue
                if hn == a or (len(a) >= 2 and a in hn):
                    out[field] = idx
                    used.add(idx)
                    break
            if field in out:
                break
    return out


def col_letter_to_idx(ref):
    letters = re.match(r"([A-Z]+)", ref)
    if not letters:
        return 0
    n = 0
    for ch in letters.group(1):
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def read_xlsx(path, sheet_index=0):
    """用标准库解析 xlsx 第一个（或指定）工作表，返回二维字符串数组"""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(f"{NS}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{NS}t")))
        sheets = sorted(n for n in names if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
        if not sheets:
            raise ValueError("xlsx 内未找到工作表")
        target = sheets[min(sheet_index, len(sheets) - 1)]
        root = ET.fromstring(z.read(target))
        rows = []
        for row in root.iter(f"{NS}row"):
            cells = {}
            for c in row.findall(f"{NS}c"):
                ref = c.get("r", "")
                idx = col_letter_to_idx(ref)
                t = c.get("t")
                v = c.find(f"{NS}v")
                if t == "s" and v is not None:
                    val = shared[int(v.text)] if v.text and int(v.text) < len(shared) else ""
                elif t == "inlineStr":
                    is_el = c.find(f"{NS}is")
                    val = "".join(x.text or "" for x in is_el.iter(f"{NS}t")) if is_el is not None else ""
                else:
                    val = v.text if v is not None else ""
                cells[idx] = (val or "").strip()
            width = max(cells) + 1 if cells else 0
            rows.append([cells.get(i, "") for i in range(width)])
        return rows


def read_table(path, sheet_index=0):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        return read_xlsx(path, sheet_index)
    if ext == ".xls":
        raise ValueError("不支持旧版 .xls，请另存为 .xlsx 或 CSV 后重试")
    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(4096)
        f.seek(0)
        delim = ","
        if sample.count("\t") > sample.count(","):
            delim = "\t"
        return [row for row in csv.reader(f, delimiter=delim)]


def pick(row, idx):
    if idx is None or idx >= len(row):
        return ""
    return (row[idx] or "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--out", default="points.json")
    ap.add_argument("--product-key", default="")
    ap.add_argument("--sheet", type=int, default=0)
    ap.add_argument("--header-row", type=int, default=0, help="表头所在行（0 起）")
    args = ap.parse_args()

    if not os.path.exists(args.file):
        print(f"文件不存在：{args.file}")
        return 1
    try:
        rows = read_table(args.file, args.sheet)
    except Exception as e:
        print(f"读取失败：{e}")
        return 1
    if len(rows) <= args.header_row + 1:
        print("表格为空或只有表头，无法解析")
        return 1

    header = rows[args.header_row]
    hmap = build_header_map(header)
    warnings = []
    if "tag" not in hmap and "name" not in hmap:
        warnings.append("未识别到测点编码/名称列，请检查表头或使用 templates/pointtable_template.csv 结构")
    for required, label in [("channel", "采集通道/寄存器地址"), ("dataType", "数据类型"), ("unit", "单位")]:
        if required not in hmap:
            warnings.append(f"缺少「{label}」列，相关字段将留空，需人工补齐")

    unrecognized = [h for i, h in enumerate(header) if h and i not in set(hmap.values())]
    if unrecognized:
        warnings.append("未识别的列（已忽略）：" + "、".join(str(h) for h in unrecognized[:15]))

    points = []
    empty_tag = 0
    for r_i, row in enumerate(rows[args.header_row + 1:], start=args.header_row + 2):
        if not any((c or "").strip() for c in row):
            continue
        tag = pick(row, hmap.get("tag")) or pick(row, hmap.get("name"))
        if not tag:
            empty_tag += 1
            continue
        mp = {
            "tag": tag,
            "property": pick(row, hmap.get("property")) or None,
            "name": pick(row, hmap.get("name")) or None,
            "dataType": pick(row, hmap.get("dataType")) or None,
            "channel": pick(row, hmap.get("channel")) or None,
            "slave": pick(row, hmap.get("slave")) or None,
            "funcCode": pick(row, hmap.get("funcCode")) or None,
            "byteOrder": pick(row, hmap.get("byteOrder")) or None,
            "scale": pick(row, hmap.get("scale")) or None,
            "offset": pick(row, hmap.get("offset")) or None,
            "unit": pick(row, hmap.get("unit")) or None,
            "min": pick(row, hmap.get("min")) or None,
            "max": pick(row, hmap.get("max")) or None,
            "range": pick(row, hmap.get("range")) or None,
            "sampleInterval": pick(row, hmap.get("sampleInterval")) or None,
            "deadband": pick(row, hmap.get("deadband")) or None,
            "qualityCode": pick(row, hmap.get("quality")) or None,
            "location": pick(row, hmap.get("location")) or None,
            "alarm": pick(row, hmap.get("alarm")) or None,
            "_row": r_i,
        }
        points.append(mp)

    if empty_tag:
        warnings.append(f"{empty_tag} 行缺少测点编码/名称，已跳过")
    dup = {}
    for mp in points:
        dup[mp["tag"]] = dup.get(mp["tag"], 0) + 1
    dups = [t for t, c in dup.items() if c > 1]
    if dups:
        warnings.append("测点编码重复：" + "、".join(dups[:10]))

    result = {"productKey": args.product_key or None, "source": os.path.basename(args.file),
              "count": len(points), "measurementPoints": points, "warnings": warnings}

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # Markdown 表
    cols = [("tag", "测点编码"), ("property", "属性"), ("dataType", "类型"), ("channel", "通道地址"),
            ("byteOrder", "字节序"), ("scale", "系数"), ("unit", "单位"), ("min", "下限"), ("max", "上限"),
            ("sampleInterval", "周期(s)"), ("location", "位置")]
    print(f"| {' | '.join(c[1] for c in cols)} |")
    print("|" + "|".join(["---"] * len(cols)) + "|")
    for mp in points:
        print("| " + " | ".join(str(mp.get(k) or "") for k, _ in cols) + " |")

    print(f"\n解析完成：{len(points)} 个测点 → {args.out}")
    for w in warnings:
        print(f"⚠️ {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
