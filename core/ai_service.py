import logging
import json
from openai import OpenAI
from config.settings import settings

logger = logging.getLogger(__name__)

def configure_deepseek_client():
    """配置DeepSeek/OpenAI client."""
    api_key = settings.DEEPSEEK_API_KEY
    if not api_key:
        logger.error("DEEPSEEK_API_KEY not found in settings. Please check your .env file.")
        return None
    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1"
        )
        return client
    except Exception as e:
        logger.error(f"Failed to configure DeepSeek client: {e}")
        return None

client = configure_deepseek_client()
MODEL_NAME = "deepseek-chat"

def evaluate_answer(question: str, correct_answer: str, user_answer: str) -> dict | None:
    """
    使用 DeepSeek 来评估用户的答案与正确答案的对比。

    :param question: quiz的问题
    :param correct_answer: 参考答案
    :param user_answer: 用户回答（回顾反思）
    :return: 'AI评估' 和'AI反馈'字典，出错则为空
    """
    if not client:
        logger.error("AI client is not configured. Cannot evaluate answer.")
        return None

    system_prompt = """
    You are an expert academic tutor. Your task is to evaluate a student's answer for a quiz question.
    Carefully compare the "User's Answer" to the "Reference Answer" in the context of the "Quiz Question".
    Determine the correctness of the user's answer. The evaluation must be one of these exact options: ["正确", "部分正确", "错误", "概念混淆"].
    Provide concise, constructive feedback. Explain why the answer is correct or incorrect, highlighting key concepts the user missed or misunderstood.
    Your final output must be a single, valid JSON object with two keys: "evaluation" and "feedback". Do not include any other text or explanations outside of the JSON structure.
    """
    
    user_prompt = f"""
    **Quiz Question:**
    {question}

    **Reference Answer:**
    {correct_answer}

    **User's Answer:**
    {user_answer}
    """

    try:
        logger.info("Sending request to DeepSeek API for answer evaluation...")
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=MODEL_NAME,
            response_format={"type": "json_object"},
        )
        
        response_text = chat_completion.choices[0].message.content
        logger.debug(f"Raw AI response: {response_text}")

        result = json.loads(response_text)
        
        if "evaluation" not in result or "feedback" not in result:
            raise ValueError("AI response JSON is missing required keys ('evaluation', 'feedback').")
            
        logger.info(f"Successfully evaluated answer. Result: {result['evaluation']}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON from AI response: {e}. Response was: {response_text}")
        return None
    except Exception as e:
        logger.error(f"An error occurred while calling the DeepSeek API: {e}")
        return None
