import pandas as pd
import pickle
import gradio as gr

from fastchat.constants import SURVEY_LINK

deprecated_model_name = [
    "gemini-1.5-pro-exp-0801",
    "gemini-1.5-pro-api-0409-preview",
    "bard-jan-24-gemini-pro",
    "chatgpt-4o-latest-20240808",
]

key_to_category_name = {
    "full": "Overall",
    "full_style_control": "Overall w/ Style Control",
    "dedup": "De-duplicate Top Redundant Queries (soon to be default)",
    "math": "Math",
    "if": "Instruction Following",
    "multiturn": "Multi-Turn",
    "coding": "Coding",
    "coding_style_control": "Coding w/ Style Control",
    "hard_6": "Hard Prompts (Overall)",
    "hard_english_6": "Hard Prompts (English)",
    "hard_6_style_control": "Hard Prompts (Overall) w/ Style Control",
    "long_user": "Longer Query",
    "english": "English",
    "chinese": "Chinese",
    "french": "French",
    "german": "German",
    "spanish": "Spanish",
    "russian": "Russian",
    "japanese": "Japanese",
    "korean": "Korean",
    "no_tie": "Exclude Ties",
    "no_short": "Exclude Short Query (< 5 tokens)",
    "no_refusal": "Exclude Refusal",
    "overall_limit_5_user_vote": "overall_limit_5_user_vote",
    "full_old": "Overall (Deprecated)",
    "full_style_control": "Overall (Style Control)",
    "hard_6_style_control": "Hard Prompts (Overall) (Style Control)",
}
cat_name_to_explanation = {
    "Overall": "Overall Questions",
    "Overall w/ Style Control": "Overall with Style Control",
    "De-duplicate Top Redundant Queries (soon to be default)": "De-duplicate top redundant queries (top 0.1%). See details in [blog post](https://lmsys.org/blog/2024-05-17-category-hard/#note-enhancing-quality-through-de-duplication).",
    "Math": "Math",
    "Instruction Following": "Instruction Following",
    "Multi-Turn": "Multi-Turn Conversation (>= 2 turns)",
    "Coding": "Coding: whether conversation contains code snippets",
    "Coding w/ Style Control": "Coding with Style Control",
    "Hard Prompts (Overall)": "Hard Prompts (Overall): details in [blog post](https://lmsys.org/blog/2024-05-17-category-hard/)",
    "Hard Prompts (Overall) w/ Style Control": "Hard Prompts (Overall) with Style Control",
    "Hard Prompts (English)": "Hard Prompts (English), note: the delta is to English Category. details in [blog post](https://lmsys.org/blog/2024-05-17-category-hard/)",
    "Longer Query": "Longer Query (>= 500 tokens)",
    "English": "English Prompts",
    "Chinese": "Chinese Prompts",
    "French": "French Prompts",
    "German": "German Prompts",
    "Spanish": "Spanish Prompts",
    "Russian": "Russian Prompts",
    "Japanese": "Japanese Prompts",
    "Korean": "Korean Prompts",
    "Exclude Ties": "Exclude Ties and Bothbad",
    "Exclude Short Query (< 5 tokens)": "Exclude Short User Query (< 5 tokens)",
    "Exclude Refusal": 'Exclude model responses with refusal (e.g., "I cannot answer")',
    "overall_limit_5_user_vote": "overall_limit_5_user_vote",
    "Overall (Deprecated)": "Overall without De-duplicating Top Redundant Queries (top 0.1%). See details in [blog post](https://lmsys.org/blog/2024-05-17-category-hard/#note-enhancing-quality-through-de-duplication).",
    "Overall (Style Control)": "Overall Leaderboard with Style Control. See details in [blog post](https://lmsys.org/blog/2024-08-28-style-control/).",
    "Hard Prompts (Overall) (Style Control)": "Hard Prompts (Overall) Leaderboard with Style Control. See details in [blog post](https://lmsys.org/blog/2024-08-28-style-control/).",
}
cat_name_to_baseline = {
    "Hard Prompts (English)": "English",
}

notebook_url = (
    "https://colab.research.google.com/drive/1KdwokPjirkTmpO_P1WByFNFiqxWQquwH"
)

basic_component_values = [None] * 6
leader_component_values = [None] * 5


def make_default_md_1(mirror=False):
    leaderboard_md = f"""
    # 🏆 LLM-jp Chatbot Arena リーダーボード
    """
    return leaderboard_md


def make_default_md_2(mirror=False):
    mirror_str = "<span style='color: red; font-weight: bold'>This is a mirror of the live leaderboard created and maintained at <a href='https://lmarena.ai/leaderboard' style='color: #B00020; text-decoration: none;'>https://lmarena.ai/leaderboard</a>. Please link to the original URL for citation purposes.</span>"
    leaderboard_md = f"""
{mirror_str if mirror else ""}

LLM-jp Chatbot Arena は、日本語 LLM を評価するためのプラットフォームです。
ユーザから収集した2つの LLM の応答のうちどちらが優れているかの投票に基づき、LLM の性能のランキングを行います。
**LLM-jp Chatbot Arena はユーザの投票に支えられています。投票へのご協力よろしくお願いいたします。**

{SURVEY_LINK}
"""

    return leaderboard_md


def make_arena_leaderboard_md(arena_df, last_updated_time, vision=False):
    total_votes = sum(arena_df["num_battles"]) // 2
    total_models = len(arena_df)
    space = "&nbsp;&nbsp;&nbsp;"

    leaderboard_md = f"""
モデル数: **{total_models}**.{space} 投票数: **{"{:,}".format(total_votes)}**.{space} 最終更新: {last_updated_time}.
"""

    leaderboard_md += f"""
[LLM-jp Chatbot Arena](https://chatbot-arena.apps.llmc.nii.ac.jp/) での投票によってレートが変動します。投票へのご協力よろしくお願いいたします。
"""
    return leaderboard_md


def make_category_arena_leaderboard_md(arena_df, arena_subset_df, name="Overall"):
    total_votes = sum(arena_df["num_battles"]) // 2
    total_models = len(arena_df)
    space = "&nbsp;&nbsp;&nbsp;"
    total_subset_votes = sum(arena_subset_df["num_battles"]) // 2
    total_subset_models = len(arena_subset_df)
    leaderboard_md = f"""### {cat_name_to_explanation[name]}
#### {space} #models: **{total_subset_models} ({round(total_subset_models/total_models *100)}%)** {space} #votes: **{"{:,}".format(total_subset_votes)} ({round(total_subset_votes/total_votes * 100)}%)**{space}
"""
    return leaderboard_md


def make_full_leaderboard_md():
    leaderboard_md = """
Three benchmarks are displayed: **Arena Elo**, **MT-Bench** and **MMLU**.
- [Chatbot Arena](https://lmarena.ai) - a crowdsourced, randomized battle platform. We use 1M+ user votes to compute model strength.
- [MT-Bench](https://arxiv.org/abs/2306.05685): a set of challenging multi-turn questions. We use GPT-4 to grade the model responses.
- [MMLU](https://arxiv.org/abs/2009.03300) (5-shot): a test to measure a model's multitask accuracy on 57 tasks.

💻 Code: The MT-bench scores (single-answer grading on a scale of 10) are computed by [fastchat.llm_judge](https://github.com/lm-sys/FastChat/tree/main/fastchat/llm_judge).
The MMLU scores are mostly computed by [InstructEval](https://github.com/declare-lab/instruct-eval).
Higher values are better for all benchmarks. Empty cells mean not available.
"""
    return leaderboard_md


def make_leaderboard_md_live(elo_results):
    leaderboard_md = f"""
# Leaderboard
Last updated: {elo_results["last_updated_datetime"]}
{elo_results["leaderboard_table"]}
"""
    return leaderboard_md


def arena_hard_title(date):
    arena_hard_title = f"""
Last Updated: {date}

**Arena-Hard-Auto v0.1** - an automatic evaluation tool for instruction-tuned LLMs with 500 challenging user queries curated from Chatbot Arena. 

We prompt GPT-4-Turbo as judge to compare the models' responses against a baseline model (default: GPT-4-0314). If you are curious to see how well your model might perform on Chatbot Arena, we recommend trying Arena-Hard-Auto. Check out our paper for more details about how Arena-Hard-Auto works as an fully automated data pipeline converting crowdsourced data into high-quality benchmarks ->
[[Paper](https://arxiv.org/abs/2406.11939) | [Repo](https://github.com/lm-sys/arena-hard-auto)]
    """
    return arena_hard_title
