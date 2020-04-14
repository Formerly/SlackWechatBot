# Crashlytics 信息发送到企业微信
## 原理

* 主要原理是通过 Slack 接收 Crashlytics 后,通过云服务 nginx 接收转发,利用脚本将 Crashlytics 信息内容 发送到 企业微信

## 搭建
* 具体搭建环境脚本参考链接:
* http://t.cn/A6wfkthK

## 主要文件
* 主要解析和运行内容在于该工程 [app.py](https://github.com/Formerly/SlackWechatBot/blob/master/app.py) 文件内.

## 运行结果
![](https://i.imgur.com/2GLCeYs.jpg)
![](https://i.imgur.com/yCm29Bi.jpg)



