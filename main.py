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
INITIAL_PROBABILITY = 0.05  # 初始概率 5%，确保平均每二十次发言至少禁言一次
PROBABILITY_INCREMENT = 0.025  # 每次增加 2.5%
MAX_PROBABILITY = 1  # 最大概率 100%
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


# 添加新的函数来管理参与用户
def get_participants(group_id):
    participants_file = os.path.join(DATA_DIR, f"{group_id}_participants.json")
    if os.path.exists(participants_file):
        with open(participants_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_participants(group_id, participants):
    participants_file = os.path.join(DATA_DIR, f"{group_id}_participants.json")
    with open(participants_file, "w", encoding="utf-8") as f:
        json.dump(participants, f)


def add_participant(group_id, user_id):
    participants = get_participants(group_id)
    if user_id not in participants:
        participants.append(user_id)
        save_participants(group_id, participants)
        return True
    return False


# 添加一个新的函数来处理用户退出
def remove_participant(group_id, user_id):
    participants = get_participants(group_id)
    if user_id in participants:
        participants.remove(user_id)
        save_participants(group_id, participants)
        return True
    return False


# 群消息处理函数
async def handle_MuteWheel_group_message(websocket, msg):
    # 确保数据目录存在
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        user_id = str(msg.get("user_id"))
        group_id = str(msg.get("group_id"))
        raw_message = str(msg.get("raw_message"))
        message_id = str(msg.get("message_id"))
        authorized = user_id in owner_id

        # 开关
        if raw_message == "mw":
            await toggle_function_status(websocket, group_id, message_id, authorized)
            return

        # 处理加入轮盘赌
        if raw_message == "mwjoin":

            if add_participant(group_id, user_id):
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]✅成功加入轮盘赌！请注意发言~",
                )
            else:
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]你已经在轮盘赌名单中了哦~",
                )
            return

        # 处理退出轮盘赌
        if raw_message == "mwquit":
            if remove_participant(group_id, user_id):
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]✅成功退出轮盘赌！你可以安全发言了~",
                )
            else:
                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]你还没有加入轮盘赌，无需退出~",
                )
            return

        # 检查是否开启
        if load_function_status(group_id):
            # 检查用户是否参与轮盘赌
            if user_id not in get_participants(group_id):
                return

            current_prob = get_current_probability(group_id)

            # 随机判定是否触发禁言
            if random.random() < current_prob:
                # 获取所有参与轮盘赌的用户
                participants = get_participants(group_id)
                # 移除当前发言用户
                if user_id in participants:
                    participants.remove(user_id)

                # 如果还有其他参与者
                if participants:
                    # 随机选择一个用户禁言
                    target_user_id = random.choice(participants)
                    # 随机禁言时间（秒）
                    mute_time = random.randint(MUTE_TIME_RANGE[0], MUTE_TIME_RANGE[1])

                    # 执行禁言
                    await set_group_ban(websocket, group_id, target_user_id, mute_time)

                    # 发送消息通知
                    await send_group_msg(
                        websocket,
                        group_id,
                        f"[CQ:reply,id={message_id}]🎯[CQ:at,qq={user_id}]的发言触发了轮盘赌！[CQ:at,qq={target_user_id}]被禁言{mute_time}秒\n当前概率: {current_prob:.1%}",
                    )

                    # 重置概率
                    reset_probability(group_id)
                else:
                    # 没有其他参与者，增加概率
                    new_prob = current_prob + PROBABILITY_INCREMENT
                    if new_prob > MAX_PROBABILITY:
                        new_prob = MAX_PROBABILITY
                    save_current_probability(group_id, new_prob)
            else:
                # 增加概率
                new_prob = current_prob + PROBABILITY_INCREMENT
                if new_prob > MAX_PROBABILITY:
                    new_prob = MAX_PROBABILITY
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
