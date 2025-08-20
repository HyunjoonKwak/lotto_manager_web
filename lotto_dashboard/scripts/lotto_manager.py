#!/usr/bin/env python3
import os, sys
# add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import argparse, json
from app import create_app
from app.extensions import db
from app.models import Draw, Recommendation
from app.utils.recommend import recommend_full, recommend_semi

def cmd_recommend(args):
    app = create_app()
    with app.app_context():
        draws = Draw.query.order_by(Draw.round.asc()).all()
        full = recommend_full(draws, 5)
        semi = recommend_semi(draws, 5)
        for combo in full:
            db.session.add(Recommendation(type="full", nums=",".join(map(str, combo)), method="freq", note="cli"))
        for triple in semi:
            db.session.add(Recommendation(type="semi", nums=",".join(map(str, triple)), method="freq", note="cli"))
        db.session.commit()
        print(json.dumps({"full": full, "semi": semi}, ensure_ascii=False, indent=2))

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("recommend")
    args = p.parse_args()
    if args.cmd == "recommend":
        cmd_recommend(args)
    else:
        p.print_help()

if __name__ == "__main__":
    main()
