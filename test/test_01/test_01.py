# test_workflow.py
from state import app


def test_consult():
    """测试产品咨询功能"""
    initial_state = {
        "messages": [{"role": "user", "content": "你们有什么手机壳产品？"}],
        "order_id": None,
        "intent": "",
        "refund_reason": "",
        "human_needed": False
    }

    result = app.invoke(initial_state)
    print("产品咨询测试结果:")
    print(f"意图识别: {result['intent']}")
    print(f"回复内容: {result['messages'][-1]['content']}")


def test_logistics_with_order():
    """测试有订单号的物流查询"""
    initial_state = {
        "messages": [{"role": "user", "content": "我想查一下物流状态，订单号是12345"}],
        "order_id": "12345",
        "intent": "",
        "refund_reason": "",
        "human_needed": False
    }

    result = app.invoke(initial_state)
    print("\n物流查询测试结果:")
    print(f"意图识别: {result['intent']}")
    print(f"回复内容: {result['messages'][-1]['content']}")


def test_refund():
    """测试退款流程"""
    initial_state = {
        "messages": [{"role": "user", "content": "我要申请退款"}],
        "order_id": None,
        "intent": "",
        "refund_reason": "",
        "human_needed": False
    }

    result = app.invoke(initial_state)
    print("\n退款申请测试结果:")
    print(f"意图识别: {result['intent']}")
    print(f"回复内容: {result['messages'][-1]['content']}")
    print(f"是否需要人工介入: {result['human_needed']}")


if __name__ == "__main__":
    test_consult()
    test_logistics_with_order()
    test_refund()
