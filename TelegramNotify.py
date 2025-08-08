import requests

class TelegramNotify:
    def __init__(self, token, chat_id=None):
        self.url = 'https://api.telegram.org'
        self.get_chatid = f'/bot{token}/getUpdates'
        self.send_message = f'/bot{token}/sendMessage'
        self.send_photo = f'/bot{token}/sendPhoto'
        self.send_sticker = f'/bot{token}/sendSticker'
        self.chat_id = None
        if chat_id is not None and chat_id != '':
            self.chat_id = chat_id
        else:
            self.chat_id = self.Get_ChatID()
            self.Send_Text('chat_id: ' + str(self.chat_id))

    def Get_ChatID(self):
        try:
            if self.chat_id is not None:
                return self.chat_id
            session = requests.Session()
            session_get = session.get(self.url + self.get_chatid)
            if session_get.status_code != 200:
                print('Error get chat_id from telegram, try again')
                return None
            if session_get.json()['ok'] is not True:
                print('Error get chat_id from telegram, try again')
                return None
            if len(session_get.json()['result']) == 0:
                print('Chat ID not found, try /start in telegrame bot and restart the program')
                return None
            chat_id = session_get.json()['result'][0]['message']['chat']['id']
            if not chat_id:
                print('Chat ID not found, try /start in telegrame bot and restart the program')
                return None
            self.chat_id = chat_id
        except Exception as ex:
            self.chat_id = None
            print(ex)
        return self.chat_id

    def Send_Text(self, text, parse_mode=None):
        try:
            params = {'chat_id': self.chat_id, 'text': text}
            if parse_mode is not None:
                params['parse_mode'] = parse_mode
            session = requests.Session()
            session_post = session.post(self.url + self.send_message, params=params)
            # print(session_post.text)
        except Exception as ex:
            print(ex)

    def Send_Image(self, caption, image_path, show_caption_above_media=True):
        try:
            params = {'chat_id': self.chat_id}
            if caption is not None and caption != '':
                params['caption'] = caption
                params['show_caption_above_media'] = show_caption_above_media
            file_img = {'photo': open(image_path, 'rb')}
            session = requests.Session()
            session_post = session.post(self.url + self.send_photo, params=params, files=file_img)
            # print(session_post.text)
        except Exception as ex:
            print(ex)

    def Send_Sticker(self, file_unique_id):
        try:
            params = {'chat_id': self.chat_id, 'sticker': file_unique_id}
            session = requests.Session()
            session_post = session.post(self.url + self.send_sticker, params=params)
            # print(session_post.text)
        except Exception as ex:
            print(ex)

    def send(self, text, image_path=None, show_caption_above_media=True, sticker_id=None, package_id=None, parse_mode=None):
        if text:
            self.Send_Text(text, parse_mode=parse_mode)
        if image_path is not None:
            self.Send_Image('', image_path, show_caption_above_media)
        if sticker_id is not None:
            self.Send_Sticker(sticker_id)