import os
import logging
import requests
import json
import sys
import time
import urllib.parse

from flask import Flask
from slack import WebClient
from slackeventsapi import SlackEventAdapter
import ssl as ssl_lib
import certifi
from onboarding_tutorial import OnboardingTutorial

# Initialize a Flask app to host the events adapter
app = Flask(__name__)
slack_events_adapter = SlackEventAdapter(os.environ['SLACK_SIGNING_SECRET'], "/slack/events", app)

wechat_webhook = os.environ['WECHAT_BOT_WEBHOOK']

# Initialize a Web API client
slack_web_client = WebClient(token=os.environ['SLACK_BOT_TOKEN'])

# For simplicity we'll store our app data in-memory with the following data structure.
# onboarding_tutorials_sent = {"channel": {"user_id": OnboardingTutorial}}
onboarding_tutorials_sent = {}


def start_onboarding(user_id: str, channel: str):
    # Create a new onboarding tutorial.
    onboarding_tutorial = OnboardingTutorial(channel)

    # Get the onboarding message payload
    message = onboarding_tutorial.get_message_payload()

    # Post the onboarding message in Slack
    response = slack_web_client.chat_postMessage(**message)

    # Capture the timestamp of the message we've just posted so
    # we can use it to update the message after a user
    # has completed an onboarding task.
    onboarding_tutorial.timestamp = response["ts"]

    # Store the message sent in onboarding_tutorials_sent
    if channel not in onboarding_tutorials_sent:
        onboarding_tutorials_sent[channel] = {}
    onboarding_tutorials_sent[channel][user_id] = onboarding_tutorial


# ================ Team Join Event =============== #
# When the user first joins a team, the type of the event will be 'team_join'.
# Here we'll link the onboarding_message callback to the 'team_join' event.
@slack_events_adapter.on("team_join")
def onboarding_message(payload):
    """Create and send an onboarding welcome message to new users. Save the
    time stamp of this message so we can update this message in the future.
    """
    event = payload.get("event", {})

    # Get the id of the Slack user associated with the incoming event
    user_id = event.get("user", {}).get("id")

    # Open a DM with the new user.
    response = slack_web_client.im_open(user_id)
    channel = response["channel"]["id"]

    # Post the onboarding message.
    start_onboarding(user_id, channel)


# ============= Reaction Added Events ============= #
# When a users adds an emoji reaction to the onboarding message,
# the type of the event will be 'reaction_added'.
# Here we'll link the update_emoji callback to the 'reaction_added' event.
@slack_events_adapter.on("reaction_added")
def update_emoji(payload):
    """Update the onboarding welcome message after receiving a "reaction_added"
    event from Slack. Update timestamp for welcome message as well.
    """
    event = payload.get("event", {})

    channel_id = event.get("item", {}).get("channel")
    user_id = event.get("user")

    if channel_id not in onboarding_tutorials_sent:
        return

    # Get the original tutorial sent.
    onboarding_tutorial = onboarding_tutorials_sent[channel_id][user_id]

    # Mark the reaction task as completed.
    onboarding_tutorial.reaction_task_completed = True

    # Get the new message payload
    message = onboarding_tutorial.get_message_payload()

    # Post the updated message in Slack
    updated_message = slack_web_client.chat_update(**message)

    # Update the timestamp saved on the onboarding tutorial object
    onboarding_tutorial.timestamp = updated_message["ts"]


# =============== Pin Added Events ================ #
# When a users pins a message the type of the event will be 'pin_added'.
# Here we'll link the update_pin callback to the 'reaction_added' event.
@slack_events_adapter.on("pin_added")
def update_pin(payload):
    """Update the onboarding welcome message after receiving a "pin_added"
    event from Slack. Update timestamp for welcome message as well.
    """
    event = payload.get("event", {})

    channel_id = event.get("channel_id")
    user_id = event.get("user")

    # Get the original tutorial sent.
    onboarding_tutorial = onboarding_tutorials_sent[channel_id][user_id]

    # Mark the pin task as completed.
    onboarding_tutorial.pin_task_completed = True

    # Get the new message payload
    message = onboarding_tutorial.get_message_payload()

    # Post the updated message in Slack
    updated_message = slack_web_client.chat_update(**message)

    # Update the timestamp saved on the onboarding tutorial object
    onboarding_tutorial.timestamp = updated_message["ts"]


# ============== Message Events ============= #
# When a user sends a DM, the event type will be 'message'.
# Here we'll link the message callback to the 'message' event.
@slack_events_adapter.on("message")
def message(payload):
    """Display the onboarding welcome message after receiving a message
    that contains "start".
    """
    print('payload原始数据:',payload)
    event = payload.get("event", {})
    channel_id = event.get('channel')
    user_id = event.get('user')
    timestamp = payload.get('event_time')
    time_local = time.localtime(timestamp)
    dt = time.strftime("%Y-%m-%d %H:%M:%S", time_local)
    # 该内容是一个集合
    attachments = event.get('attachments')

    if attachments != None:
        attachmentsItem = attachments[0]
        text = attachmentsItem.get('fallback')
        if text == None:
            text = 'null'
        # 取出信息集合内容
        fields = attachmentsItem.get('fields')
        # 终端类型
        platformValue = ''
        # 异常版本
        version = ''
        # 明确信息地址
        summary = ''
        if fields != None:
         for fieldsItem in fields:
                title = fieldsItem.get('title')
                if title == 'Summary':
                    summary = fieldsItem.get('value')

                if title == 'Platform':
                    platformValue = fieldsItem.get('value')

                if title == 'Version':
                    version = fieldsItem.get('value')              
        # 对崩溃链接做截取,方便传递Markdown语法使用
        summary = summary[1:len(summary) - 1]
        # 如果带有空格的URL,会是以 | 为开始 后面跟着对应简洁的堆栈
        index = summary.find('|')
        # 获得崩溃的具体信息内容
        crashDetail = summary[index + 1:len(summary)]
        # 避免URL携带空格导致MD语法展示异常,把裁剪后的内容保留源URL
        summary = summary[0:index]

        # 发送明细md信息
        postText = '<font color=\"warning\">' + text + '</font>\n\n' + '发生了异常崩溃,请相关同事注意。\n\n>' + '崩溃终端:<font color=\"warning\">' + platformValue + '</font>\n\n>' + \
            '版本号:<font color=\"warning\">' + version + '</font>\n\n>' + \
            '崩溃时间:<font color=\"warning\">' + dt + \
            '</font>\n\n>' + '崩溃信息:' + '[' + crashDetail + '](' + summary + ')'
        sendWorkWechatMessage(postText)

    else:
        text = event.get('text')
        if text == None:
            text = 'null'
        postText ='<font color=\"warning\">' + text + '</font>\n\n' + '异常信息,请相关同事注意。'+ '\n>' + '异常时间:<font color=\"warning\">' + dt + '</font>'         
        sendWorkWechatMessage(postText)

    if text and text.lower() == "start":
        return start_onboarding(user_id, channel_id)


def sendWorkWechatMessage(content):
    #json序列化
    data = json.dumps({"msgtype": "markdown", "markdown":{'content':content}})
    print('data:',data)
    r = requests.post(wechat_webhook, data, auth=('Content-Type', 'application/json'))

if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())
    ssl_context = ssl_lib.create_default_context(cafile=certifi.where())
    app.run(port=3000)
