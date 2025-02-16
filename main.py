# script/MuteWheel/main.py

import logging
import os
import sys
import re
import json
import random  # 添加random模块导入

# 添加项目根目录到sys.path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.config import *
from app.api import send_group_msg, set_group_ban
from app.switch import load_switch, save_switch


# 数据存储路径，实际开发时，请将MuteWheel替换为具体的数据存放路径
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "MuteWheel",
)

# 在DATA_DIR定义后修改MUTE_TIME_RANGE常量
INITIAL_PROBABILITY = 0.01  # 初始概率 1%
PROBABILITY_INCREMENT = 0.01  # 每次增加 1%
MAX_PROBABILITY = 0.50  # 最大概率 50%
MUTE_TIME_RANGE = (1, 10)  # 禁言时间范围（秒）


# 查看功能开关状态
def load_function_status(group_id):
    return load_switch(group_id, "MuteWheel")


# 保存功能开关状态
def save_function_status(group_id, status):
    save_switch(group_id, "MuteWheel", status)


# 处理元事件，用于启动时确保数据目录存在
async def handle_MuteWheel_meta_event(websocket):
    os.makedirs(DATA_DIR, exist_ok=True)


# 处理开关状态
async def toggle_function_status(websocket, group_id, message_id, authorized):
    if not authorized:
        await send_group_msg(
            websocket,
            group_id,
            f"[CQ:reply,id={message_id}]❌❌❌你没有权限对MuteWheel功能进行操作,请联系管理员。",
        )
        return

    if load_function_status(group_id):
        save_function_status(group_id, False)
        await send_group_msg(
            websocket,
            group_id,
            f"[CQ:reply,id={message_id}]🚫🚫🚫MuteWheel功能已关闭",
        )
    else:
        save_function_status(group_id, True)
        await send_group_msg(
            websocket, group_id, f"[CQ:reply,id={message_id}]✅✅✅MuteWheel功能已开启"
        )


# 获取当前群的概率
def get_current_probability(group_id):
    prob_file = os.path.join(DATA_DIR, f"{group_id}_probability.json")
    if os.path.exists(prob_file):
        with open(prob_file, "r", encoding="utf-8") as f:
            return float(json.load(f)["probability"])
    return INITIAL_PROBABILITY


# 保存当前群的概率
def save_current_probability(group_id, probability):
    prob_file = os.path.join(DATA_DIR, f"{group_id}_probability.json")
    with open(prob_file, "w", encoding="utf-8") as f:
        json.dump({"probability": probability}, f)


# 重置概率
def reset_probability(group_id):
    save_current_probability(group_id, INITIAL_PROBABILITY)


# 群消息处理函数
async def handle_MuteWheel_group_message(websocket, msg):
    # 确保数据目录存在
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        user_id = str(msg.get("user_id"))
        group_id = str(msg.get("group_id"))
        raw_message = str(msg.get("raw_message"))
        role = str(msg.get("sender", {}).get("role"))
        message_id = str(msg.get("message_id"))
        authorized = user_id in owner_id

        # 开关
        if raw_message == "mw":
            await toggle_function_status(websocket, group_id, message_id, authorized)
            return
        # 检查是否开启
        if load_function_status(group_id):
            # 管理员和机器人自己不参与轮盘赌
            if role in ["admin", "owner"] or user_id in owner_id:
                return

            current_prob = get_current_probability(group_id)

            # 随机判定是否禁言
            if random.random() < current_prob:
                # 随机禁言时间（秒）
                mute_time = random.randint(MUTE_TIME_RANGE[0], MUTE_TIME_RANGE[1])

                # 执行禁言（直接使用秒数）
                await set_group_ban(websocket, group_id, user_id, mute_time)

                # 发送消息通知（修改提示信息为秒）
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]🎯命中！禁言{mute_time}秒\n当前概率: {current_prob:.1%}",
                )

                # 重置概率
                reset_probability(group_id)
            else:
                # 增加概率
                new_prob = min(current_prob + PROBABILITY_INCREMENT, MAX_PROBABILITY)
                save_current_probability(group_id, new_prob)

                # 可选：发送当前概率提示
                # if random.random() < 0.1:  # 10%概率显示提示
                #     await send_group_msg(
                #         websocket, group_id, f"当前禁言概率: {new_prob:.1%}"
                #     )
    except Exception as e:
        logging.error(f"处理MuteWheel群消息失败: {e}")
        await send_group_msg(
            websocket,
            group_id,
            "处理MuteWheel群消息失败，错误信息：" + str(e),
        )
        return


# 统一事件处理入口
async def handle_events(websocket, msg):
    """统一事件处理入口"""
    post_type = msg.get("post_type", "response")  # 添加默认值
    try:
        # 处理回调事件
        if msg.get("status") == "ok":
            pass

        post_type = msg.get("post_type")

        # 处理元事件
        if post_type == "meta_event":
            await handle_MuteWheel_meta_event(websocket)

        # 处理消息事件
        elif post_type == "message":
            message_type = msg.get("message_type")
            if message_type == "group":
                await handle_MuteWheel_group_message(websocket, msg)
            elif message_type == "private":
                return

        # 处理通知事件
        elif post_type == "notice":
            if msg.get("notice_type") == "group":
                return

    except Exception as e:
        error_type = {
            "message": "消息",
            "notice": "通知",
            "request": "请求",
            "meta_event": "元事件",
        }.get(post_type, "未知")

        logging.error(f"处理MuteWheel{error_type}事件失败: {e}")

        # 发送错误提示
        if post_type == "message":
            message_type = msg.get("message_type")
            if message_type == "group":
                await send_group_msg(
                    websocket,
                    msg.get("group_id"),
                    f"处理MuteWheel{error_type}事件失败，错误信息：{str(e)}",
                )
