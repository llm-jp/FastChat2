"""
Chatbot Arena (battle) tab.
Users chat with two anonymous models.
"""

import copy
import json
import time

import gradio as gr
import numpy as np

from fastchat.constants import (
    MODERATION_MSG,
    CONVERSATION_LIMIT_MSG,
    SLOW_MODEL_MSG,
    BLIND_MODE_INPUT_CHAR_LEN_LIMIT,
    CONVERSATION_TURN_LIMIT,
    SURVEY_LINK,
)
from fastchat.serve.gradio_block_arena_named import flash_buttons
from fastchat.serve.gradio_web_server import (
    State,
    bot_response,
    get_conv_log_filename,
    no_change_btn,
    enable_btn,
    disable_btn,
    invisible_btn,
    enable_text,
    disable_text,
    disable_radio,
    visible_radio,
    invisible_radio,
    acknowledgment_md,
    get_ip,
    get_model_description_md,
)
from fastchat.serve.remote_logger import get_remote_logger
from fastchat.utils import (
    build_logger,
    moderation_filter,
)

logger = build_logger("gradio_web_server_multi", "gradio_web_server_multi.log")

num_sides = 2
enable_moderation = False
anony_names = ["", ""]
models = []


def set_global_vars_anony(enable_moderation_):
    global enable_moderation
    enable_moderation = enable_moderation_


def load_demo_side_by_side_anony(models_, url_params):
    global models
    models = models_

    states = (None,) * num_sides
    selector_updates = (
        gr.Markdown(visible=True),
        gr.Markdown(visible=True),
    )

    return states + selector_updates


def vote_last_response(states, vote_type, model_selectors, request: gr.Request):
    with open(get_conv_log_filename(), "a") as fout:
        data = {
            "tstamp": round(time.time(), 4),
            "type": vote_type,
            "models": [x for x in model_selectors],
            "states": [x.dict() for x in states],
            "ip": get_ip(request),
        }
        fout.write(json.dumps(data) + "\n")
    get_remote_logger().log(data)

    gr.Info(
        "🎉 投票ありがとうございます！"
    )

    if vote_type == "leftvote":
        context_selector = "モデル A"
    elif vote_type == "rightvote":
        context_selector = "モデル B"
    else:
        context_selector = None

    yield (disable_btn,) * 4 + (context_selector,)


def leftvote_last_response(
    state0, state1, model_selector0, model_selector1, request: gr.Request
):
    logger.info(f"leftvote (anony). ip: {get_ip(request)}")
    for x in vote_last_response(
        [state0, state1], "leftvote", [model_selector0, model_selector1], request
    ):
        yield x


def rightvote_last_response(
    state0, state1, model_selector0, model_selector1, request: gr.Request
):
    logger.info(f"rightvote (anony). ip: {get_ip(request)}")
    for x in vote_last_response(
        [state0, state1], "rightvote", [model_selector0, model_selector1], request
    ):
        yield x


def tievote_last_response(
    state0, state1, model_selector0, model_selector1, request: gr.Request
):
    logger.info(f"tievote (anony). ip: {get_ip(request)}")
    for x in vote_last_response(
        [state0, state1], "tievote", [model_selector0, model_selector1], request
    ):
        yield x


def bothbad_vote_last_response(
    state0, state1, model_selector0, model_selector1, request: gr.Request
):
    logger.info(f"bothbad_vote (anony). ip: {get_ip(request)}")
    for x in vote_last_response(
        [state0, state1], "bothbad_vote", [model_selector0, model_selector1], request
    ):
        yield x


def regenerate(state0, state1, request: gr.Request):
    logger.info(f"regenerate (anony). ip: {get_ip(request)}")
    states = [state0, state1]
    if state0.regen_support and state1.regen_support:
        for i in range(num_sides):
            states[i].conv.update_last_message(None)
        return (
            states + [x.to_gradio_chatbot() for x in states] + [""] + [disable_btn] * 7
        )
    states[0].skip_next = True
    states[1].skip_next = True
    return states + [x.to_gradio_chatbot() for x in states] + [""] + [no_change_btn] * 7


def clear_history(request: gr.Request):
    logger.info(f"clear_history (anony). ip: {get_ip(request)}")
    return (
        [None] * num_sides
        + [None] * num_sides
        + anony_names
        + [enable_text]
        + [invisible_btn] * 4
        + [disable_btn] * 3
        + [""]
        + [enable_btn]
        + [invisible_radio]
    )


def share_click(state0, state1, model_selector0, model_selector1, request: gr.Request):
    logger.info(f"share (anony). ip: {get_ip(request)}")
    if state0 is not None and state1 is not None:
        vote_last_response(
            [state0, state1], "share", [model_selector0, model_selector1], request
        )


def disclose_models(state0, state1):
    return (
        [f"### モデル A: {state0.model_name}", f"### モデル B: {state1.model_name}"]  # model_selectors
        +[disable_text]  # textbox
        + [disable_btn] * 4  # vote buttons
        + [disable_btn]  # send_btn
        + [disable_btn]  # regenerate_btn
        + [enable_btn]  # clear_btn
        + [disable_radio]  # context_selector
        + [disable_btn]  # disclose_btn
    )


def enable_buttons():
    return [enable_btn] * 7


SAMPLING_WEIGHTS = {}

# target model sampling weights will be boosted.
BATTLE_TARGETS = {}

ANON_MODELS = []

SAMPLING_BOOST_MODELS = []

# outage models won't be sampled.
OUTAGE_MODELS = []


def get_sample_weight(model, outage_models, sampling_weights, sampling_boost_models=[]):
    if model in outage_models:
        return 0
    if len(sampling_weights) == 0:
        return 1
    weight = sampling_weights.get(model, 0)
    if model in sampling_boost_models:
        weight *= 5
    return weight


def get_battle_pair(
    models, battle_targets, outage_models, sampling_weights, sampling_boost_models, model_a_name=None
):
    if len(models) == 1:
        return models[0], models[0]

    if model_a_name and model_a_name != "ランダム":
        chosen_model = model_a_name
    else:
        model_weights = []
        for model in models:
            weight = get_sample_weight(
                model, outage_models, sampling_weights, sampling_boost_models
            )
            model_weights.append(weight)
        total_weight = np.sum(model_weights)
        model_weights = model_weights / total_weight
        chosen_idx = np.random.choice(len(models), p=model_weights)
        chosen_model = models[chosen_idx]
        # for p, w in zip(models, model_weights):
        #     print(p, w)

    rival_models = []
    rival_weights = []
    for model in models:
        if model == chosen_model:
            continue
        if model in ANON_MODELS and chosen_model in ANON_MODELS:
            continue
        weight = get_sample_weight(model, outage_models, sampling_weights)
        if (
            weight != 0
            and chosen_model in battle_targets
            and model in battle_targets[chosen_model]
        ):
            # boost to 20% chance
            weight = 0.5 * total_weight / len(battle_targets[chosen_model])
        rival_models.append(model)
        rival_weights.append(weight)
    # for p, w in zip(rival_models, rival_weights):
    #     print(p, w)
    rival_weights = rival_weights / np.sum(rival_weights)
    rival_idx = np.random.choice(len(rival_models), p=rival_weights)
    rival_model = rival_models[rival_idx]

    return chosen_model, rival_model


def add_text(
    state0,
    state1,
    text,
    context_selector,
    model_a_name,
    request: gr.Request,
):
    ip = get_ip(request)
    logger.info(f"add_text (anony). ip: {ip}. len: {len(text)}")
    states = [state0, state1]

    # Init states if necessary
    is_initial = False
    if states[0] is None:
        assert states[1] is None

        model_left, model_right = get_battle_pair(
            models,
            BATTLE_TARGETS,
            OUTAGE_MODELS,
            SAMPLING_WEIGHTS,
            SAMPLING_BOOST_MODELS,
            model_a_name=model_a_name,
        )
        states = [
            State(model_left),
            State(model_right),
        ]

        is_initial = True

    if len(text) <= 0:
        gr.Warning("メッセージを入力してください")
        for i in range(num_sides):
            states[i].skip_next = True
        return (
            states  # states
            + [x.to_gradio_chatbot() for x in states]  # chatbots
            + [""]  # textbox
            + [no_change_btn] * 7  # btn_list
            + [""]  # slow_warning
            + [visible_radio if states[0].conv.messages else invisible_radio]  # context_selector
        )

    if context_selector is None and states[0].conv.messages:
        gr.Warning("どちらの応答に対して会話を続けるか選択してください")
        for i in range(num_sides):
            states[i].skip_next = True
        return (
            states  # states
            + [x.to_gradio_chatbot() for x in states]  # chatbots
            + [text]  # textbox
            + [no_change_btn] * 7  # btn_list
            + [""]  # slow_warning
            + [visible_radio]  # context_selector
        )

    # Apply the chosen context
    if context_selector:
        if context_selector == "モデル A":
            chosen_context = states[0].conv.messages
        elif context_selector == "モデル B":
            chosen_context = states[1].conv.messages
        else:
            raise ValueError("Invalid model")
        for i in range(num_sides):
            states[i].conv.messages = copy.deepcopy(chosen_context)

    # NOTE: We disable moderation check as we use Chatbot Arena for internal testing.
    # model_list = [states[i].model_name for i in range(num_sides)]
    # # turn on moderation in battle mode
    # all_conv_text_left = states[0].conv.get_prompt()
    # all_conv_text_right = states[0].conv.get_prompt()
    # all_conv_text = (
    #     all_conv_text_left[-1000:] + all_conv_text_right[-1000:] + "\nuser: " + text
    # )
    # flagged = moderation_filter(all_conv_text, model_list, do_moderation=True)
    # if flagged:
    #     logger.info(f"violate moderation (anony). ip: {ip}. text: {text}")
    #     # overwrite the original text
    #     text = MODERATION_MSG

    conv = states[0].conv
    if (len(conv.messages) - conv.offset) // 2 >= CONVERSATION_TURN_LIMIT:
        logger.info(f"ターン数の限界です ip: {get_ip(request)}. text: {text}")
        for i in range(num_sides):
            states[i].skip_next = True
        return (
            states  # states
            + [x.to_gradio_chatbot() for x in states]  # chatbots
            + [CONVERSATION_LIMIT_MSG]  # textbox
            + [no_change_btn] * 7  # btn_list
            + [""]  # warning
            + [visible_radio]  # context_selector
        )

    text = text[:BLIND_MODE_INPUT_CHAR_LEN_LIMIT]  # Hard cut-off
    for i in range(num_sides):
        states[i].conv.append_message(states[i].conv.roles[0], text)
        states[i].conv.append_message(states[i].conv.roles[1], None)
        states[i].skip_next = False

    hint_msg = ""
    for i in range(num_sides):
        if "deluxe" in states[i].model_name:
            hint_msg = SLOW_MODEL_MSG
    
    # Update the model A name if specified
    if is_initial and model_a_name and model_a_name != "ランダム":
        chatbot_updates = [
            gr.Chatbot(
                states[0].to_gradio_chatbot(),
                label=f"モデル A: {model_a_name}",
            ),
            states[1].to_gradio_chatbot(),
        ]
    else:
        chatbot_updates = [
            states[0].to_gradio_chatbot(),
            states[1].to_gradio_chatbot(),
        ]

    return (
        states  # states
        + chatbot_updates  # chatbots
        + [""]  # textbox
        + [disable_btn] * 7  # btn_list
        + [hint_msg]  # slow_warning
        + [visible_radio]  # context_selector
    )


def bot_response_multi(
    state0,
    state1,
    temperature,
    top_p,
    max_new_tokens,
    request: gr.Request,
):
    logger.info(f"bot_response_multi (anony). ip: {get_ip(request)}")

    if state0 is None or state0.skip_next:
        # This generate call is skipped due to invalid inputs
        yield (
            [state0, state1]  # states
            + [state0.to_gradio_chatbot(), state1.to_gradio_chatbot()]  # chatbots
            + [no_change_btn] * 7  # btn_list
        )
        return

    states = [state0, state1]
    gen = []
    for i in range(num_sides):
        gen.append(
            bot_response(
                states[i],
                temperature,
                top_p,
                max_new_tokens,
                request,
                apply_rate_limit=False,
                use_recommended_config=True,
            )
        )

    model_tpy = []
    for i in range(num_sides):
        token_per_yield = 1
        if states[i].model_name in [
            "gemini-pro",
            "gemma-1.1-2b-it",
            "gemma-1.1-7b-it",
            "phi-3-mini-4k-instruct",
            "phi-3-mini-128k-instruct",
            "snowflake-arctic-instruct",
        ]:
            token_per_yield = 30
        elif states[i].model_name in [
            "qwen-max-0428",
            "qwen1.5-110b-chat",
            "llava-v1.6-34b",
        ]:
            token_per_yield = 7
        elif states[i].model_name in [
            "qwen2-72b-instruct",
        ]:
            token_per_yield = 4
        model_tpy.append(token_per_yield)

    chatbots = [None] * num_sides
    iters = 0
    while True:
        stop = True
        iters += 1
        for i in range(num_sides):
            try:
                # yield fewer times if chunk size is larger
                if model_tpy[i] == 1 or (iters % model_tpy[i] == 1 or iters < 3):
                    ret = next(gen[i])
                    states[i], chatbots[i] = ret[0], ret[1]
                stop = False
            except StopIteration:
                pass
        yield states + chatbots + [disable_btn] * 7
        if stop:
            break


def build_side_by_side_ui_anony(models):
    notice_markdown = f"""
# ⚔️  LLM-jp Chatbot Arena

## 📜 使い方
- 2つの匿名モデルと会話し、より優れていると思う応答に投票してください。
- 会話を続けるには、どちらの応答に対して会話を続けるかを選択してください。各モデルは選択された応答を前のターンに生成したものとして、次の応答を生成します。
- モデル名を表示するには「モデル名を表示」を押して下さい。モデル名を表示すると、会話は終了し、投票できなくなります。
"""

    states = [gr.State() for _ in range(num_sides)]
    model_selectors = [None] * num_sides
    chatbots = [None] * num_sides

    gr.Markdown(notice_markdown, elem_id="notice_markdown")

    with gr.Group(elem_id="share-region-anony"):
        with gr.Accordion(
            f"🔍 対応している {len(models)} 個のモデルのリストを見る", open=False
        ):
            model_description_md = get_model_description_md(models)
            gr.Markdown(model_description_md, elem_id="model_description_markdown")
        with gr.Row():
            model_a_name = gr.Dropdown(
                ["ランダム"] + models,
                label="🈯 モデル A を指定する",
                elem_id="model_a_selector",
            )
        with gr.Row():
            for i in range(num_sides):
                label = "モデル A" if i == 0 else "モデル B"
                with gr.Column():
                    chatbots[i] = gr.Chatbot(
                        label=label,
                        elem_id="chatbot",
                        height=650,
                        show_copy_button=True,
                    )

        with gr.Row():
            for i in range(num_sides):
                with gr.Column():
                    model_selectors[i] = gr.Markdown(
                        anony_names[i], elem_id="model_selector_md"
                    )
        with gr.Row():
            slow_warning = gr.Markdown("")

    with gr.Row():
        leftvote_btn = gr.Button(
            value="👈  Aの方が良い", visible=False, interactive=False
        )
        rightvote_btn = gr.Button(
            value="👉  Bの方が良い", visible=False, interactive=False
        )
        tie_btn = gr.Button(value="🤝  どちらも良い", visible=False, interactive=False)
        bothbad_btn = gr.Button(
            value="👎  どちらも悪い", visible=False, interactive=False
        )
    
    with gr.Row():
        disclose_btn = gr.Button(
            value="モデル名を表示（※会話は終了し、投票できなくなります）",
            visible=False,
        )

    with gr.Row():
        context_selector = gr.Radio(
            choices=["モデル A", "モデル B"],
            label="会話を続ける応答を選択してください",
            elem_id="context_selector",
            visible=False,
        )

    with gr.Row():
        textbox = gr.Textbox(
            show_label=False,
            placeholder="👉 メッセージを入力して送信を押して下さい",
            elem_id="input_box",
        )
        send_btn = gr.Button(value="送信", variant="primary", scale=0)

    with gr.Row() as button_row:
        clear_btn = gr.Button(value="🎲 はじめから", interactive=False)
        regenerate_btn = gr.Button(value="🔄  もう一度生成", interactive=False)
        # share_btn = gr.Button(value="📷  Share")

    with gr.Accordion("Parameters", open=False, visible=False) as parameter_row:
        temperature = gr.Slider(
            minimum=0.0,
            maximum=1.0,
            value=0.6,
            step=0.1,
            interactive=True,
            label="Temperature",
        )
        top_p = gr.Slider(
            minimum=0.0,
            maximum=1.0,
            value=0.9,
            step=0.1,
            interactive=True,
            label="Top P",
        )
        max_output_tokens = gr.Slider(
            minimum=16,
            maximum=2048,
            value=1600,
            step=64,
            interactive=True,
            label="Max output tokens",
        )

    gr.Markdown(acknowledgment_md, elem_id="ack_markdown")

    # Register listeners
    btn_list = [
        leftvote_btn,
        rightvote_btn,
        tie_btn,
        bothbad_btn,
        disclose_btn,
        regenerate_btn,
        clear_btn,
    ]
    leftvote_btn.click(
        leftvote_last_response,
        states + model_selectors,
        [leftvote_btn, rightvote_btn, tie_btn, bothbad_btn, context_selector],
    )
    rightvote_btn.click(
        rightvote_last_response,
        states + model_selectors,
        [leftvote_btn, rightvote_btn, tie_btn, bothbad_btn, context_selector],
    )
    tie_btn.click(
        tievote_last_response,
        states + model_selectors,
        [leftvote_btn, rightvote_btn, tie_btn, bothbad_btn, context_selector],
    )
    bothbad_btn.click(
        bothbad_vote_last_response,
        states + model_selectors,
        [leftvote_btn, rightvote_btn, tie_btn, bothbad_btn, context_selector],
    )
    regenerate_btn.click(
        regenerate, states, states + chatbots + [textbox] + btn_list
    ).then(
        bot_response_multi,
        states + [temperature, top_p, max_output_tokens],
        states + chatbots + btn_list,
    ).then(
        enable_buttons, [], btn_list
    )
    clear_btn.click(
        clear_history,
        None,
        states
        + chatbots
        + model_selectors
        + [textbox]
        + btn_list
        + [slow_warning]
        + [send_btn]
        + [context_selector],
    )

#     share_js = """
# function (a, b, c, d) {
#     const captureElement = document.querySelector('#share-region-anony');
#     html2canvas(captureElement)
#         .then(canvas => {
#             canvas.style.display = 'none'
#             document.body.appendChild(canvas)
#             return canvas
#         })
#         .then(canvas => {
#             const image = canvas.toDataURL('image/png')
#             const a = document.createElement('a')
#             a.setAttribute('download', 'chatbot-arena.png')
#             a.setAttribute('href', image)
#             a.click()
#             canvas.remove()
#         });
#     return [a, b, c, d];
# }
# """
#     share_btn.click(share_click, states + model_selectors, [], js=share_js)

    textbox.submit(
        add_text,
        states + [textbox] + [context_selector] + [model_a_name],
        states + chatbots + [textbox] + btn_list + [slow_warning] + [context_selector],
    ).then(
        bot_response_multi,
        states + [temperature, top_p, max_output_tokens],
        states + chatbots + btn_list,
    ).then(
        enable_buttons, [], btn_list
    )

    send_btn.click(
        add_text,
        states + [textbox] + [context_selector],
        states + chatbots + [textbox] + btn_list + [slow_warning] + [context_selector],
    ).then(
        bot_response_multi,
        states + [temperature, top_p, max_output_tokens],
        states + chatbots + btn_list,
    ).then(
        enable_buttons, [], btn_list
    )

    disclose_btn.click(
        disclose_models,
        states,
        model_selectors + [
            textbox,
            leftvote_btn,
            rightvote_btn,
            tie_btn,
            bothbad_btn,
            send_btn,
            regenerate_btn,
            clear_btn,
            context_selector,
            disclose_btn,
        ],
    )

    return states + model_selectors
