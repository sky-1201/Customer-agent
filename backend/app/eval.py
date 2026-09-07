"""分流评测脚本：golden set 测分流准确率（召回率优先）

用法（在 backend 目录下）：
    python -m app.eval

指标（对应技术文档 3.4 节，优先级从高到低）：
- complaint_recall：投诉召回率，目标 100%（漏一个投诉都不可接受）
- complex_recall：复杂售后召回率，目标 >95%
- fast_path_precision：快速通道"真简单"比例，目标 >90%
"""
from langchain_core.messages import SystemMessage

from app.graph.router import ROUTER_PROMPT, router_llm, rule_triage
from app.utils.logger import get_logger

logger = get_logger("eval")

# golden set：30 条标注消息（query → 期望分类）
GOLDEN_SET = [
    # simple（10 条）
    ("怎么激活系统", "simple"),
    ("能开发票吗", "simple"),
    ("这款电脑重量多少", "simple"),
    ("预算5000办公用推荐哪款", "simple"),
    ("发货后多久能到", "simple"),
    ("笔记本怎么连接WiFi", "simple"),
    ("保修需要什么凭证", "simple"),
    ("电脑发热正常吗", "simple"),
    ("第一次开机需要设置什么", "simple"),
    ("这款和小新Pro16哪个好", "simple"),
    ("过保了还能修吗", "simple"),
    # complex（10 条）
    ("蓝屏修两次要换货", "complex"),
    ("修了两次还是蓝屏，能不能换新的", "complex"),
    ("屏幕有坏点可以换吗", "complex"),
    ("电池鼓包了，能免费换吗", "complex"),
    ("同一故障修了三次，要求退货", "complex"),
    ("风扇异响送修过一次又响了", "complex"),
    ("充不进电修了两次还是不行", "complex"),
    ("键盘失灵修过一次又坏了，要换货", "complex"),
    ("三包期内修两次可以换货吗", "complex"),
    # complaint（10 条）
    ("我要投诉你们", "complaint"),
    ("我要投诉到12315", "complaint"),
    ("你们售后太差了，要曝光", "complaint"),
    ("我要给差评", "complaint"),
    ("服务态度太差，我要投诉", "complaint"),
    ("我要退一赔三", "complaint"),
    ("我要找消协投诉", "complaint"),
    ("骗子，我要投诉", "complaint"),
    ("再不解决我就曝光你们", "complaint"),
    ("态度太差了，给我个说法，不然投诉", "complaint"),
]


def classify(text: str) -> str:
    """分流（和 router_node 一致的三层逻辑：规则 → LLM → 置信度兜底）"""
    # 第1层：规则快筛
    rule_result = rule_triage(text)
    if rule_result:
        return rule_result

    # 第2层：LLM 分类（小模型）
    result = router_llm.invoke([SystemMessage(content=ROUTER_PROMPT), ("user", text)])

    # 第3层：置信度兜底
    if result.intent == "complaint":
        return "complaint"
    if result.confidence < 0.7:
        return "complex"
    return result.intent


def evaluate():
    """跑评测，输出三个指标 + 错分明细"""
    complaint_total = complaint_hit = 0
    complex_total = complex_hit = 0
    simple_predicted = simple_correct = 0
    errors = []

    for text, expected in GOLDEN_SET:
        predicted = classify(text)

        if expected == "complaint":
            complaint_total += 1
            if predicted == "complaint":
                complaint_hit += 1
        elif expected == "complex":
            complex_total += 1
            if predicted == "complex":
                complex_hit += 1
        if predicted == "simple":
            simple_predicted += 1
            if expected == "simple":
                simple_correct += 1

        if predicted != expected:
            errors.append(f"  ✗ '{text}' → 期望 {expected}，实际 {predicted}")

    complaint_recall = complaint_hit / complaint_total if complaint_total else 1.0
    complex_recall = complex_hit / complex_total if complex_total else 1.0
    fast_path_precision = simple_correct / simple_predicted if simple_predicted else 1.0

    print("=" * 56)
    print("分流评测结果（golden set 共 30 条）")
    print("=" * 56)
    print(f"投诉召回率     complaint_recall     = {complaint_recall:.1%}  目标 100%")
    print(f"复杂召回率     complex_recall       = {complex_recall:.1%}  目标 >95%")
    print(f"快速通道精确率  fast_path_precision  = {fast_path_precision:.1%}  目标 >90%")
    print()
    if errors:
        print(f"错分 {len(errors)} 条：")
        for e in errors:
            print(e)
    else:
        print("全部正确 ✓")


if __name__ == "__main__":
    evaluate()
