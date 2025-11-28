#!/usr/bin/env python3
"""
讯飞星火大模型测试脚本

交互式对话测试，支持流式输出。

用法:
    python scripts/test_spark.py

或者设置环境变量:
    export SPARK_APPID=your_app_id
    export SPARK_API_SECRET=your_api_secret
    export SPARK_API_KEY=your_api_key
    python scripts/test_spark.py
"""

import asyncio
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.llm.spark_client import SparkClient, SparkClientError

# ============== 配置区域 ==============
# 方式1: 直接在这里配置（不推荐提交到代码仓库）
SPARK_CONFIG = {
    "app_id": "YOUR_APP_ID",
    "api_secret": "YOUR_API_SECRET",
    "api_key": "YOUR_API_KEY",
    "spark_url": "wss://spark-api.xf-yun.com/chat/pro-128k",
    "domain": "pro-128k",
}

# 方式2: 从环境变量读取（推荐）
def get_config():
    return {
        "app_id": os.getenv("SPARK_APPID", SPARK_CONFIG["app_id"]),
        "api_secret": os.getenv("SPARK_API_SECRET", SPARK_CONFIG["api_secret"]),
        "api_key": os.getenv("SPARK_API_KEY", SPARK_CONFIG["api_key"]),
        "spark_url": os.getenv("SPARK_URL", SPARK_CONFIG["spark_url"]),
        "domain": os.getenv("SPARK_DOMAIN", SPARK_CONFIG["domain"]),
    }


# ============== 主程序 ==============

async def single_turn_test():
    """单轮对话测试"""
    config = get_config()
    client = SparkClient(**config)

    print("\n" + "=" * 50)
    print("单轮对话测试")
    print("=" * 50)

    test_messages = [
        {"role": "user", "content": "你好，请用一句话介绍一下你自己。"}
    ]

    print(f"\n用户: {test_messages[0]['content']}")
    print("\n星火: ", end="", flush=True)

    try:
        async for chunk in client.chat_stream(test_messages):
            print(chunk, end="", flush=True)
        print("\n")
    except SparkClientError as e:
        print(f"\n错误: {e}")
        return False

    return True


async def multi_turn_test():
    """多轮对话测试"""
    config = get_config()
    client = SparkClient(**config)

    print("\n" + "=" * 50)
    print("多轮对话测试")
    print("=" * 50)

    conversation = [
        {"role": "user", "content": "我是一名环保工程师，正在做水质监测项目。"},
    ]

    # 第一轮
    print(f"\n用户: {conversation[0]['content']}")
    print("\n星火: ", end="", flush=True)

    response1 = []
    async for chunk in client.chat_stream(conversation):
        print(chunk, end="", flush=True)
        response1.append(chunk)
    print("\n")

    # 添加助手回复和新问题
    conversation.append({"role": "assistant", "content": "".join(response1)})
    conversation.append({"role": "user", "content": "COD超标可能是什么原因导致的？"})

    # 第二轮
    print(f"用户: {conversation[-1]['content']}")
    print("\n星火: ", end="", flush=True)

    async for chunk in client.chat_stream(conversation):
        print(chunk, end="", flush=True)
    print("\n")


async def interactive_chat():
    """交互式对话"""
    config = get_config()
    client = SparkClient(**config, temperature=0.7)

    print("\n" + "=" * 50)
    print("交互式对话模式")
    print("输入 'quit' 或 'exit' 退出")
    print("输入 'clear' 清空对话历史")
    print("=" * 50)

    conversation = []
    system_prompt = "你是 EcoMind 环保智能助手，专注于环境监测、污染治理和生态保护领域。请用专业但易懂的语言回答问题。"

    while True:
        try:
            user_input = input("\n你: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit"]:
                print("\n再见！")
                break

            if user_input.lower() == "clear":
                conversation = []
                print("\n对话历史已清空。")
                continue

            conversation.append({"role": "user", "content": user_input})

            print("\n星火: ", end="", flush=True)

            response_chunks = []
            try:
                async for chunk in client.chat_stream(
                    conversation, system_prompt=system_prompt
                ):
                    print(chunk, end="", flush=True)
                    response_chunks.append(chunk)
                print()

                # 保存助手回复到对话历史
                conversation.append(
                    {"role": "assistant", "content": "".join(response_chunks)}
                )

            except SparkClientError as e:
                print(f"\n错误: {e}")
                # 移除失败的用户消息
                conversation.pop()

        except KeyboardInterrupt:
            print("\n\n再见！")
            break


async def connection_test():
    """连接测试"""
    config = get_config()
    client = SparkClient(**config)

    print("\n" + "=" * 50)
    print("连接测试")
    print("=" * 50)

    print("\n正在测试连接...")

    if await client.test_connection():
        print("✓ 连接成功！")
        return True
    else:
        print("✗ 连接失败，请检查配置。")
        return False


async def main():
    """主入口"""
    print("\n" + "=" * 50)
    print("讯飞星火大模型 (Spark Pro-128K) 测试工具")
    print("=" * 50)

    config = get_config()
    print(f"\nAPPID: {config['app_id']}")
    print(f"URL: {config['spark_url']}")
    print(f"Domain: {config['domain']}")

    while True:
        print("\n请选择测试模式:")
        print("1. 连接测试")
        print("2. 单轮对话测试")
        print("3. 多轮对话测试")
        print("4. 交互式对话")
        print("5. 退出")

        try:
            choice = input("\n请输入选项 (1-5): ").strip()

            if choice == "1":
                await connection_test()
            elif choice == "2":
                await single_turn_test()
            elif choice == "3":
                await multi_turn_test()
            elif choice == "4":
                await interactive_chat()
            elif choice == "5":
                print("\n再见！")
                break
            else:
                print("无效选项，请重新输入。")

        except KeyboardInterrupt:
            print("\n\n再见！")
            break


if __name__ == "__main__":
    asyncio.run(main())
