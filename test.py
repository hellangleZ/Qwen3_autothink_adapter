import openai
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import re

# --- Definition of the Filter class (adapted for synchronous use and openai.Client) ---
class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=0, description="Priority level for the filter operations."
        )
        max_turns: int = Field(
            default=99999,
            description="Maximum allowable conversation turns for a user.",
        )

    class UserValves(BaseModel):
        max_turns: int = Field(
            default=99999,
            description="Maximum allowable conversation turns for a user.",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.assessment_model_name: str = "Qwen3-30B-A3B" # 您脚本中使用的模型

    def inlet(
        self,
        body: Dict[str, Any],
        openai_client: openai.Client,
        __user__: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        messages = body.get("messages", [])

        if not messages:
            print("Filter.inlet: 消息列表为空，直接返回。")
            return body

        latest_user_msg_obj = next(
            (msg for msg in reversed(messages) if msg.get("role") == "user"), None
        )

        if not latest_user_msg_obj:
            print("Filter.inlet: 未找到最新的用户消息，直接返回。")
            return body
        
        original_latest_user_msg_content = latest_user_msg_obj.get("content", "")
        
        user_request_str = original_latest_user_msg_content

        if len(user_request_str) > 1024:  
            print("Filter.inlet: 用户请求过长，进行截断处理。")
            user_request_str = user_request_str[:500] + "\n\n" + user_request_str[-500:]

        assessment_messages = [
            {
                "role": "system",
                "content": """You are a specialized AI model acting as a Request Difficulty Assessor.
Your SOLE and ONLY task is to evaluate the inherent difficulty of a user's request that is intended for another AI.
You will receive a user's request message.
Your objective is to determine if this request requires careful, deliberate thought from the downstream AI, or if it's straightforward.

Criteria for your decision:
1. If the user's request is complex, nuanced, requires multi-step reasoning, creative generation, in-depth analysis, or careful consideration by the AI to produce a high-quality response, you MUST respond with: `hard`
2. If the user's request is simple, factual, straightforward, or can likely be answered quickly and directly by the AI with minimal processing or deliberation, you MUST respond with: `easy`

IMPORTANT:
- Your response MUST be EXACTLY one of the two commands: `hard` or `easy`.
- Your response MUST start with either `hard` or `easy`.
- Do NOT add any other text, explanations, or pleasantries.
- Your assessment is about the processing difficulty for the *AI that will ultimately handle the user's request*.
---
### User's request:
<Users_request>\n""" + user_request_str + "\n</Users_request>",
            },
        ]

        print(f"Filter.inlet: 正在调用评估LLM (模型: {self.assessment_model_name}) 判断难度...")
        api_reply_processed = "unknown"

        try:
            assessment_response = openai_client.chat.completions.create(
                model=self.assessment_model_name,
                messages=assessment_messages,
                temperature=0.1,
                # max_tokens parameter removed, server will use its default
                extra_body={ # *** NEW: Added extra_body for classifier call ***
                    "chat_template_kwargs": {"enable_thinking": False}
                }
            )
            
            assessment_message_obj = assessment_response.choices[0].message
            raw_api_reply = assessment_message_obj.content
            
            if raw_api_reply is None:
                assessment_message_data = assessment_message_obj.model_dump() 
                raw_api_reply = assessment_message_data.get("reasoning_content")
                if raw_api_reply:
                    print(f"Filter.inlet: 注意 - 'content'为空, 从 'reasoning_content' 获取了评估LLM原始回复: '{raw_api_reply}'")
            
            print(f"Filter.inlet: 评估LLM有效原始回复 (content或reasoning_content): '{raw_api_reply}'")

            if raw_api_reply:
                pattern = r"<think[^>]*>.*?</think>"
                cleaned_reply = re.sub(pattern, "", raw_api_reply, flags=re.DOTALL).strip().lower()
                
                if cleaned_reply == "hard":
                    api_reply_processed = "hard"
                elif cleaned_reply == "easy":
                    api_reply_processed = "easy"
                else:
                    api_reply_processed = "unknown_response"
                    print(f"Filter.inlet: 评估LLM清理后回复 '{cleaned_reply}' 非预期的 'hard' 或 'easy'。")
            else:
                api_reply_processed = "empty_response"
                print("Filter.inlet: 评估LLM的 'content' 和 (若尝试) 'reasoning_content' 均为空或无效。")

            print(f"Filter.inlet: 处理后的评估结果: '{api_reply_processed}'")

            modified_messages = [msg.copy() for msg in messages]
            
            modified_target_msg = None
            for i in reversed(range(len(modified_messages))):
                if modified_messages[i]["role"] == "user" and modified_messages[i]["content"] == original_latest_user_msg_content:
                    modified_target_msg = modified_messages[i]
                    break
            
            if not modified_target_msg:
                print("Filter.inlet: 警告 - 未能在副本中定位到要修改的用户消息。")
                body["messages"] = [msg.copy() for msg in messages]
                return body

            if api_reply_processed == "hard":
                modified_target_msg["content"] = original_latest_user_msg_content + "\n\n/think"
                print("Filter.inlet: 难度评估为 'hard', 追加 /think")
            elif api_reply_processed == "easy":
                modified_target_msg["content"] = original_latest_user_msg_content + "\n\n/no_think" # Or don't append anything if that's preferred
                print("Filter.inlet: 难度评估为 'easy', 追加 /no_think")
            else: 
                print(f"Filter.inlet: 由于评估结果为 '{api_reply_processed}', 未追加think/no_think标签。")
                modified_target_msg["content"] = original_latest_user_msg_content

            body["messages"] = modified_messages

        except Exception as e:
            print(f"Filter.inlet: 调用评估LLM时发生错误: {e}")
            body["messages"] = [msg.copy() for msg in messages]

        return body

    def outlet(self, body: Dict[str, Any], __user__: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return body

# --- Your existing script, modified to use the Filter ---

client = openai.Client(base_url="http://127.0.0.1:30000/v1", api_key="None") 

def print_highlight(text, color_code="1;33"): 
    print(f"\033[{color_code}m{text}\033[0m")

my_filter = Filter()

user_content_code = "Hello"
#user_content_code = "用torch帮我从0开始写一个LLM，需要包括数据预处理、模型构建（基于Transformer的encoder-decoder架构）、训练循环和推理部分的代码框架。"
current_user_content = user_content_code 

initial_request_body_for_filter = {
    "messages": [
        {"role": "user", "content": current_user_content},
    ],
}

print_highlight(f"原始用户请求: {initial_request_body_for_filter['messages'][0]['content']}", "1;36") 

modified_request_body_from_filter = my_filter.inlet(
    body=initial_request_body_for_filter.copy(), 
    openai_client=client
)

final_messages_for_llm = modified_request_body_from_filter.get("messages", [])

if not final_messages_for_llm:
    print_highlight("错误：Filter处理后消息列表为空！", "1;31") 
    exit()

print_highlight(f"经Filter处理后待发送给主LLM的消息内容: '{final_messages_for_llm[-1]['content']}'", "1;32")

try:
    print_highlight(f"正在调用主LLM生成最终回复...", "1;35")
    # 主LLM的调用目前没有显式设置 enable_thinking。
    # 如果需要，您也可以在这里根据 api_reply_processed 的结果来决定是否添加类似的 extra_body。
    # 例如，如果 api_reply_processed == "hard"，可以考虑设置 enable_thinking: True (如果服务器支持并且这是期望行为)
    main_response = client.chat.completions.create(
        model="Qwen3-30B-A3B",
        messages=final_messages_for_llm,
        temperature=0.7,
        top_p=0.8,
        # max_tokens parameter removed, server will use its default
    )

    main_message_obj = main_response.choices[0].message
    
    # --- 调试代码开始 ---
    raw_content_from_llm = main_message_obj.content 
    main_message_data_for_debug = main_message_obj.model_dump() 
    raw_reasoning_content_from_llm = main_message_data_for_debug.get("reasoning_content")
    
    print_highlight("DEBUG: 主LLM原始 'content' 字段内容:", "1;36")
    print(raw_content_from_llm)
    print_highlight("DEBUG: 主LLM原始 'reasoning_content' 字段内容:", "1;36")
    print(raw_reasoning_content_from_llm)
    # --- 调试代码结束 ---

    final_answer = raw_content_from_llm 

    if final_answer is None:
        final_answer = raw_reasoning_content_from_llm 
        if final_answer: 
            print_highlight("主LLM: 注意 - 'content'为空, 从 'reasoning_content' 获取了最终回复。", "1;33") 
            
    print_highlight("主LLM的最终回复 (基于上述优先级和调试中观察到的值):", "1;34") 
    print(final_answer)

except openai.APIError as e:
    print_highlight(f"主LLM API调用失败: {e}", "1;31") 
except Exception as e:
    print_highlight(f"发生未知错误: {e}", "1;31")
