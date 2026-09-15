"""Equal-weight Automated Verification Score; REVIEW and N/A are excluded."""
def compute_score(report: dict) -> dict:
    rules=report.get('rules',[]); eligible=[r for r in rules if r.get('status') in {'PASS','FAIL'}]
    passed=[r for r in eligible if r['status']=='PASS']; score=round(100*len(passed)/len(eligible)) if eligible else 0
    return {'score':score,'grade':'A' if score>=90 else 'B' if score>=75 else 'C' if score>=60 else 'D' if score>=40 else 'F','label':'Automated Verification Score','verifiable_rule_count':len(eligible),'passed_rule_count':len(passed),'failed_rule_count':len(eligible)-len(passed),'review_count':sum(r.get('status')=='REVIEW' for r in rules),'not_applicable_count':sum(r.get('status')=='N/A' for r in rules),'coverage_percent':round(100*len(eligible)/len(rules),1) if rules else 0,'category_breakdown':{r['rule_id']:{'points_earned':1 if r['status']=='PASS' else 0,'points_possible':1} for r in eligible},'deductions':{'readability':0,'notes':0}}
