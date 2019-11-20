from django.core.files.storage import Storage
from django.conf import settings
from fdfs_client.client import Fdfs_client

class FDFSStorage(Storage):
    '''fdfs 文件存储类'''
    def __init__(self,client_conf=None,base_url=None):
        '''初始化'''
        if client_conf is None:
            client_conf = settings.FDFS_CLIENT_CONF
        self.client_conf = client_conf

        if base_url is None:
            base_url = settings.FDFS_URL
        self.base_url = base_url
    def _open(self,name,mode='rb'):
        '''打开文件时使用'''
        pass
    def _save(self,name,content):
        '''保存文件时使用---上传'''
        '''
        :param name:上文的文件名
        :param content:文件内容--file对象
        :return:
        '''
        #创建fdfs_client对象
        client = Fdfs_client(self.client_conf)
        #上传文件到fdfs系统中
        res = client.upload_by_buffer(content.read())
        if res.get('Status')!='Upload successed.':
            #文件上传失败
            raise Exception('上传文件到fdfs系统失败')
        #获取返回的文件id   group1/M00/00/00/rB_KGl3De5qAFPAYAAAADXj9r-s807.txt
        filename = res.get('Romote file_id')
        return filename
    def exists(self, name):
        '''django判断文件名是否可用'''
        return False
    def url(self, name):
        '''返回访问文件的url路径'''
        return self.base_url+name







