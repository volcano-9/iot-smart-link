#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""iot-smart-link 评测运行器（零第三方依赖）。

用法:
    # 1. 把专家每次回答存成 eval/answers/<case-id>.md
    python eval/run_eval.py

    # 2. 只跑指定用例（冒烟测试用）
    python eval/run_eval.py --answers eval/samples/good --only ACC-02

    # 3. CI 模式：不达标退出码 1
    python eval/run_eval.py --strict

产物:
    eval/report.md    人读报告
    eval/report.json  机读结果
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
CN_NUM = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
CJK = re.compile(r"[\u4e00-\u9fff]")
WS = re.compile(r"\s+")


# ---------------------------------------------------------------- 文本工具
def norm(text: str) -> str:
    """折叠空白并小写，供关键词匹配。"""
    return WS.sub(" ", text).lower()


def strip_code_fences(text: str) -> str:
    """去掉 ``` 围栏代码块内容，避免代码里的符号误判为格式违规。"""
    out, in_fence = [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append(line)
    return "\n".join(out)


def heading_lines(text: str):
    """提取疑似标题行：Markdown 标题、纯加粗行、有序列表项。"""
    heads = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            heads.append(s.lstrip("# ").strip())
        elif re.match(r"^\*\*[^*]{1,40}\*\*[:：]?$", s):
            heads.append(s.strip("*:： "))
        elif re.match(r"^\d+[.、)）]\s*\S{1,30}$", s):
            heads.append(re.sub(r"^\d+[.、)）]\s*", "", s))
    return heads


def hit(alt: str, blob: str) -> bool:
    return norm(alt) in blob


def group_hit(alts, text_norm, heads_norm):
    """任一同义词命中即通过；标题优先，正文兜底。"""
    for alt in alts:
        if hit(alt, heads_norm):
            return True, "标题"
    for alt in alts:
        if hit(alt, text_norm):
            return True, "正文"
    return False, ""


def has_md_table(text: str) -> bool:
    """检测 Markdown 表格分隔行。"""
    return bool(re.search(r"^\s*\|?[\s:|-]*-{2,}[\s:|-]*\|?\s*$", text, re.M))


def meaningful_len(text: str) -> int:
    return len(WS.sub("", text))


def cjk_ratio(text: str) -> float:
    body = WS.sub("", strip_code_fences(text))
    if not body:
        return 0.0
    return len(CJK.findall(body)) / len(body)


# ---------------------------------------------------------------- 判分
def run_case(case: dict, answer: str, global_rules: dict):
    """返回 (得分, checks 明细列表, 红线明细列表)。"""
    checks = []
    tn, hn = norm(answer), norm("\n".join(heading_lines(answer)))

    # 1. 章节结构
    for alts in case.get("expect_sections", []) or []:
        ok, where = group_hit(alts, tn, hn)
        checks.append({
            "name": "章节：%s" % " / ".join(alts),
            "ok": ok,
            "detail": "命中于%s" % where if ok else "缺失",
        })

    # 2. 关键词必备组
    for alts in case.get("must_any", []) or []:
        ok, where = group_hit(alts, tn, hn)
        checks.append({
            "name": "必备：%s" % " / ".join(alts),
            "ok": ok,
            "detail": "命中于%s" % where if ok else "未提及",
        })

    # 3. 表格
    if case.get("must_table"):
        ok = has_md_table(answer)
        checks.append({"name": "含 Markdown 表格", "ok": ok,
                       "detail": "有" if ok else "无表格"})

    # 4. 禁用词
    forbidden = case.get("forbid", []) or []
    if forbidden:
        bad = [w for w in forbidden if hit(w, tn)]
        checks.append({
            "name": "无禁用表述（%s）" % "、".join(forbidden),
            "ok": not bad,
            "detail": "出现：%s" % "、".join(bad) if bad else "干净",
        })

    # 5. 最小长度
    if case.get("min_len"):
        n = meaningful_len(answer)
        ok = n >= case["min_len"]
        checks.append({"name": "实质长度 ≥ %d 字" % case["min_len"], "ok": ok,
                       "detail": "实际 %d 字" % n})

    # 6. 反问数量上限（仅对显式声明的用例生效，避免免费得分项稀释区分度）
    cap = case.get("max_questions")
    if cap:
        q = answer.count("？") + answer.count("?")
        ok = q <= cap
        checks.append({"name": "反问 ≤ %d 次" % cap, "ok": ok,
                       "detail": "实际 %d 次" % q})

    # 7. 语种一致性
    lang = case.get("lang", "zh")
    if lang == "en":
        r = cjk_ratio(answer)
        ok = r < 0.15
        checks.append({"name": "英文作答（中文占比 <15%）", "ok": ok,
                       "detail": "中文占比 %.1f%%" % (r * 100)})

    # 8. 全局格式红线
    violations = []
    clean = answer if not global_rules.get("skip_inside_code_fence") else strip_code_fences(answer)
    for ch in global_rules.get("forbid_chars", []):
        cnt = clean.count(ch)
        if cnt:
            violations.append("出现 %d 处波浪号 %r（U+%04X）" % (cnt, ch, ord(ch)))
    for pat in global_rules.get("forbid_regex", []):
        m = re.findall(pat, clean)
        if m:
            violations.append("出现删除线语法 %d 处" % len(m))
    checks.append({
        "name": "格式红线（无波浪号/删除线）",
        "ok": not violations,
        "detail": "；".join(violations) if violations else "干净",
    })

    passed = sum(1 for c in checks if c["ok"])
    base = round(100 * passed / len(checks)) if checks else 0
    penalty = min(len(violations) * global_rules.get("_penalty", 5),
                  global_rules.get("_cap", 20))
    score = max(0, base - penalty)
    return score, checks, violations


# ---------------------------------------------------------------- 报告
def grade_of(total: float, meta: dict) -> str:
    if total >= meta.get("gradeA", 90):
        return "A"
    if total >= meta.get("gradeB", 80):
        return "B"
    if total >= meta.get("gradeC", 70):
        return "C"
    return "D"


def build_report(results, meta, global_rules, answers_dir):
    ran = [r for r in results if r["ran"]]
    skipped = [r for r in results if not r["ran"]]
    total = (round(sum(r["score"] * r["weight"] for r in ran) / sum(r["weight"] for r in ran), 1)
             if ran else 0.0)
    grade = grade_of(total, meta)
    red_total = sum(len(r["violations"]) for r in ran)

    by_cat = {}
    for r in ran:
        d = by_cat.setdefault(r["category"], {"w": 0, "s": 0.0, "n": 0})
        d["w"] += r["weight"]
        d["s"] += r["score"] * r["weight"]
        d["n"] += 1

    L = []
    a = L.append
    _sec = {"n": 0}

    def sec(title):
        _sec["n"] += 1
        a("## %s、%s" % (CN_NUM[_sec["n"] - 1], title))
        a("")
    a("# %s — 评测报告" % meta["suite"])
    a("")
    a("- 专家：`%s` v%s" % (meta["expert"], meta["expertVersion"]))
    a("- 用例集：%d 条（已运行 %d 条，缺失 %d 条）"
      % (len(results), len(ran), len(skipped)))
    a("- 答案目录：`%s`" % answers_dir)
    a("- 生成时间：%s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    a("")
    sec("总评")
    a("| 指标 | 值 |")
    a("| --- | --- |")
    a("| 加权总分 | **%.1f** / 100 |" % total)
    a("| 评级 | **%s** |" % grade)
    a("| 覆盖率 | %d / %d |" % (len(ran), len(results)))
    a("| 格式红线违规 | %d 处 |" % red_total)
    a("| 达标线 | %.0f 分 |" % meta["passLine"])
    a("")
    if not ran:
        verdict = "尚无答案：请按 README 第 2 步把专家回答存到 eval/answers/<用例ID>.md 后再判分"
    elif total >= 85 and red_total == 0 and len(ran) == len(results):
        verdict = "建议提交审核"
    elif total >= 85 and red_total == 0:
        verdict = "已运行用例达标，但覆盖率仅 %d/%d，请补齐后再判定" % (len(ran), len(results))
    else:
        verdict = "不建议提交，先修复下方问题"
    a("**结论：%s**" % verdict)
    a("")

    if by_cat:
        sec("分类得分")
        a("| 分类 | 用例数 | 得分 |")
        a("| --- | --- | --- |")
        for cat, d in sorted(by_cat.items(), key=lambda kv: kv[1]["s"] / kv[1]["w"]):
            a("| %s | %d | %.1f |" % (cat, d["n"], d["s"] / d["w"]))
        a("")

    sec("用例明细")
    a("| 用例 | 标题 | 得分 | 未通过项 |")
    a("| --- | --- | --- | --- |")
    for r in results:
        if not r["ran"]:
            a("| %s | %s | 未运行 | — |" % (r["id"], r["title"]))
            continue
        fails = [c["name"] for c in r["checks"] if not c["ok"]]
        mark = "🟢" if r["score"] >= 90 else ("🟡" if r["score"] >= 75 else "🔴")
        a("| %s %s | %s | %d | %s |"
          % (r["id"], mark, r["title"], r["score"],
             "；".join(fails) if fails else "—"))
    a("")

    bad = [r for r in ran if r["score"] < meta["passLine"]]
    if bad:
        sec("未达标用例的问题清单")
        for r in sorted(bad, key=lambda x: x["score"]):
            a("### %s %s（%d 分）" % (r["id"], r["title"], r["score"]))
            a("")
            for c in r["checks"]:
                if not c["ok"]:
                    a("- ❌ %s —— %s" % (c["name"], c["detail"]))
            a("- 参考要点：")
            for rb in r["rubric"]:
                a("  - %s" % rb)
            a("")

    if red_total:
        sec("格式红线违规明细")
        a("> %s" % global_rules.get("forbid_message", ""))
        a("")
        for r in ran:
            if r["violations"]:
                a("- **%s**：%s" % (r["id"], "；".join(r["violations"])))
        a("")

    if skipped:
        sec("未运行用例")
        a("以下用例在 `%s` 中没有对应答案文件，未计入总分。" % answers_dir)
        a("")
        for r in skipped:
            a("- `%s.md` —— %s" % (r["id"], r["title"]))
        a("")

    sec("人工评审要点")
    a("自动判分只查「有没有说到」，专业判断与表述质量需人工确认。逐条对照：")
    a("")
    for r in ran:
        a("<details><summary><b>%s</b> %s</summary>" % (r["id"], r["title"]))
        a("")
        for rb in r["rubric"]:
            a("- [ ] %s" % rb)
        a("")
        a("</details>")
        a("")

    a("---")
    a("")
    a("评分规则：每个用例 100 分均摊到各项检查（章节/必备关键词/表格/禁用词/长度/反问数/语种/格式红线），"
      "再按红线命中数每次扣 %d 分（上限 %d 分）；总分按用例权重加权平均。"
      % (global_rules.get("_penalty", 5), global_rules.get("_cap", 20)))
    return "\n".join(L), total, grade, len(ran), len(skipped), red_total


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser(description="iot-smart-link 评测运行器")
    ap.add_argument("--cases", default=os.path.join(HERE, "cases.json"))
    ap.add_argument("--answers", default=os.path.join(HERE, "answers"))
    ap.add_argument("--out", default=os.path.join(HERE, "report.md"))
    ap.add_argument("--json", default=os.path.join(HERE, "report.json"))
    ap.add_argument("--only", nargs="*", help="只跑这些用例 id")
    ap.add_argument("--init", action="store_true",
                    help="为缺失答案的用例生成用例卡到 eval/prompts/，便于逐条测试")
    ap.add_argument("--strict", action="store_true", help="低于达标线时退出码 1")
    args = ap.parse_args()

    with io.open(args.cases, encoding="utf-8") as f:
        spec = json.load(f)
    meta = dict(spec["meta"])
    sc = meta.get("scoring", {}) or {}
    # 阈值统一放在 meta 顶层，便于报告与判分共用
    meta["passLine"] = sc.get("passLine", 75)
    meta["gradeA"] = sc.get("gradeA", 90)
    meta["gradeB"] = sc.get("gradeB", 80)
    meta["gradeC"] = sc.get("gradeC", 70)

    gr = dict(spec.get("global_rules", {}))
    gr["_penalty"] = sc.get("globalPenaltyPerHit", 5)
    gr["_cap"] = sc.get("globalPenaltyCap", 20)
    cases = spec["cases"]
    if args.only:
        want = {s.upper() for s in args.only}
        cases = [c for c in cases if c["id"].upper() in want]

    results = []
    if args.init:
        pdir = os.path.join(HERE, "prompts")
        if not os.path.isdir(pdir):
            os.makedirs(pdir)
        n = 0
        for c in cases:
            p = os.path.join(pdir, c["id"] + ".md")
            if os.path.isfile(p):
                continue
            body = ["# %s %s" % (c["id"], c["title"]), "",
                    "- 分类：%s　权重：%d" % (c["category"], c["weight"]), "",
                    "## 发送这句提问", "", "```text", c["prompt"], "```", "",
                    "## 存答案到", "", "`eval/answers/%s.md`（只放回答正文）" % c["id"], "",
                    "## 自动判分看什么", ""]
            for alts in c.get("expect_sections", []) or []:
                body.append("- 章节需含：%s" % " / ".join(alts))
            for alts in c.get("must_any", []) or []:
                body.append("- 必含其一：%s" % " / ".join(alts))
            if c.get("must_table"):
                body.append("- 需含 Markdown 表格")
            if c.get("forbid"):
                body.append("- 禁出现：%s" % "、".join(c["forbid"]))
            if c.get("min_len"):
                body.append("- 实质长度 ≥ %d 字" % c["min_len"])
            if c.get("max_questions"):
                body.append("- 反问 ≤ %d 次" % c["max_questions"])
            if c.get("lang") == "en":
                body.append("- 全英文作答（中文占比 <15%）")
            body += ["", "## 人工评审要点", ""]
            for rb in c.get("rubric", []):
                body.append("- [ ] %s" % rb)
            with io.open(p, "w", encoding="utf-8") as f:
                f.write("\n".join(body) + "\n")
            n += 1
        print("已生成 %d 张用例卡 -> eval/prompts/" % n)
        return

    results = []
    for c in cases:
        path = os.path.join(args.answers, c["id"] + ".md")
        if not os.path.isfile(path):
            results.append(dict(id=c["id"], title=c["title"], category=c["category"],
                                weight=c["weight"], ran=False, score=0,
                                checks=[], violations=[], rubric=c.get("rubric", []),
                                prompt=c["prompt"]))
            continue
        with io.open(path, encoding="utf-8") as f:
            ans = f.read()
        score, checks, vio = run_case(c, ans, gr)
        results.append(dict(id=c["id"], title=c["title"], category=c["category"],
                            weight=c["weight"], ran=True, score=score,
                            checks=checks, violations=vio,
                            rubric=c.get("rubric", []), prompt=c["prompt"],
                            chars=meaningful_len(ans)))

    md, total, grade, n_ran, n_skip, n_red = build_report(results, meta, gr, args.answers)
    with io.open(args.out, "w", encoding="utf-8") as f:
        f.write(md)
    with io.open(args.json, "w", encoding="utf-8") as f:
        json.dump(dict(generated_at=datetime.now().isoformat(timespec="seconds"),
                       expert=meta["expert"], version=meta["expertVersion"],
                       total=total, grade=grade, ran=n_ran, skipped=n_skip,
                       redline_violations=n_red, pass_line=meta["passLine"],
                       cases=results), f, ensure_ascii=False, indent=2)

    print("用例 %d 条 | 已运行 %d | 缺失 %d" % (len(results), n_ran, n_skip))
    for r in results:
        flag = "SKIP" if not r["ran"] else ("OK  " if r["score"] >= meta["passLine"] else "FAIL")
        print("  [%s] %-7s %3s  %s" % (flag, r["id"], "-" if not r["ran"] else r["score"], r["title"]))
    print("-" * 56)
    print("加权总分 %.1f / 100   评级 %s   红线违规 %d 处" % (total, grade, n_red))
    print("报告：%s" % args.out)

    if args.strict and (total < meta["passLine"] or n_red > 0 or n_skip > 0):
        sys.exit(1)


if __name__ == "__main__":
    main()
