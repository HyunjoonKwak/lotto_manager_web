#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
로또 당첨 판매점 HTML 덤프 병합 스크립트
- 동행복권 topStore 파싱 중 저장해 둔 table_*tbl_data.debug.html/shops_*tbl_data.debug.html 파일을 병합
- 기본 대상 디렉터리: /volume1/code_work/lotto_dashboard/logs/shops
실행 예:
  python3 merge_shops.py --round 1185
  python3 merge_shops.py --round 1185 --data-dir /volume1/code_work/lotto_dashboard/logs/shops --out /volume1/code_work/lotto_dashboard/logs/shops/shops_1185.csv
"""

import os
import glob
import argparse
from bs4 import BeautifulSoup
import pandas as pd

def parse_args():
    p = argparse.ArgumentParser(description="병합 스크립트 (tbl_data.debug.html → CSV)")
    p.add_argument("--data-dir", default="/volume1/code_work/lotto_dashboard/logs/shops",
                   help="HTML 덤프가 있는 디렉터리 (기본: logs/shops)")
    p.add_argument("--round", type=int, default=1185, help="회차 번호 (기본: 1185)")
    p.add_argument("--pattern", default="*tbl_data.debug.html",
                   help="파일 글롭 패턴 (기본: *tbl_data.debug.html)")
    p.add_argument("--out", default=None, help="출력 CSV 경로 (미지정 시 data-dir 내 자동 생성)")
    return p.parse_args()

def parse_files(data_dir: str, draw_round: int, pattern: str):
    out_rows = []
    files = glob.glob(os.path.join(data_dir, pattern))
    files.sort()
    if not files:
        print(f"⚠️ 대상 파일이 없습니다. (dir={data_dir}, pattern={pattern})")
        return out_rows

    for fname in files:
        print(f"📂 처리중: {os.path.basename(fname)}")
        with open(fname, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", {"class": "tbl_data"})
        if not table:
            continue
        tbody = table.find("tbody")
        if not tbody:
            continue
        for tr in tbody.find_all("tr"):
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            # 보통: [상호명, 소재지, 판매구분] 또는 [번호, 상호명, 소재지, 판매구분]
            if len(tds) < 3:
                continue
            # 번호 컬럼이 앞에 있는 경우 보정
            if tds[0].isdigit() and len(tds) >= 4:
                name, addr, typ = tds[1], tds[2], tds[3]
            else:
                name, addr, typ = tds[0], tds[1], tds[2] if len(tds) >= 3 else ""

            # 노이즈 가드 (이상치 몇 가지 컷)
            if not name or name.startswith("601~") or "전체 지역 상호" in name:
                continue

            out_rows.append({
                "round": draw_round,
                "store": name,
                "address": addr,
                "type": typ or "미상",
                "source": os.path.basename(fname),
            })
    return out_rows

def main():
    args = parse_args()
    rows = parse_files(args.data_dir, args.round, args.pattern)
    if not rows:
        print("🚫 데이터가 추출되지 않았습니다.")
        return

    df = pd.DataFrame(rows)
    # 간단한 정리: 공백 트림, 중복 제거
    df["store"] = df["store"].str.strip()
    df["address"] = df["address"].str.strip()
    df["type"] = df["type"].str.strip()
    df = df.drop_duplicates(subset=["round", "store", "address", "type"])

    out_path = args.out or os.path.join(args.data_dir, f"shops_{args.round}.csv")
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    # 요약 출력
    print(f"✅ 저장 완료 → {out_path}")
    print(f"   총 행수: {len(df)}")
    print("   판매구분별 건수:")
    print(df["type"].value_counts(dropna=False).to_string())

if __name__ == "__main__":
    main()
