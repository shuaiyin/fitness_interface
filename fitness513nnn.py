#!/usr/bin/env python
#-*- coding: UTF-8 -*
#coding:utf-8 
# -*- coding: utf-8 -*-
import os.path
import re
import redis
import time
import tornado.auth
import tornado.database
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import unicodedata
import sys
import random
from random import sample
#debug mode 
import tornado.autoreload 
import operator
import socket
from tornado.options import define, options
import json
reload(sys)
sys.setdefaultencoding('utf8')
#open debug mode 
define("debug",default=True,help="debug mode",type=bool)
settings = {'debug':True}
#the setting of the debug mode to print differant except sentence 
define("is_debug",default=True,help="is debug mode",type=bool)
define("port", default=8888, help="run on the given port", type=int)
define("mysql_host", default="127.0.0.1:3306", help="blog database host")
define("mysql_database", default="fitness", help="blog database name")
define("mysql_user", default="root", help="blog database user")
#the password of mysql is null
define("mysql_password", default="tZ3BtYCeQLdwyKqF", help="blog database password")

define('redis_host',default="127.0.0.1",help="redis host")
define('redis_port',default="7000",help="redis port")
define('redis_db',default="0",help="redis db")

#expire times config  
define('group_info_expires',default="3600",help="group info will clear from cache after 1 hours")
define('group_user_list_expires',default="3600",help="group_user_list will clear from cache after 1 hour")
define('user_info_expires',default="36000",help="user_info will clear from cache after 10 hours")
define('mygroup_expires',default="36000",help="the group which me is not the leader expires")
define('leadergroup_expires',default="36000",help="the group which i an the leader")
define('game_info_expires',default="36000",help="the expires of the game info is 10 hours ")
define('game_lives_expires',default="18000",help="the expires of the game lives is 5 hours ")
define('game_lives_all_expires',default="18000",help="the expires of the game lives all is 5 hours ")
define('game_intro_expires',default="18000",help="the expires of the game intro")
define('game_agreement_expires',default="18000",help="the expire of the game agreement")
define('recent_run_man',default="10",help="the expires of the 6 recent run man")
define('rank_data_expires',default="10",help="the expires of the rank_data_expires")
#
define('ipnet',default="http://101.200.214.68",help="this is the ipnet of the resourse")
define('recent_show',default="6",help="show the recent run man or group num ")
define('html_path',default="/home/yinshuai/",help="set the default html file save path")
#
define('mem_num_show',default="6",help="the num of mem show in the group page")
define('mem_point_show_num',default="5",help="the num of mem pointer show ")

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", HomeHandler),
            (r"/archive", ArchiveHandler),
            (r"/feed", FeedHandler),
            (r"/[pk]y/tag", TagHandler),
            (r"/compose", ComposeHandler),
            (r"/base",BaseHandler),
            (r"/[pk]y/test",TestHandler),
            (r"/[pk]y/group",GroupHandler), 
            (r"/[pk]y/invite",InviteHandler),
            (r"/[pk]y/apply",ApplyHandler),
            (r"/[pk]y/user",UserHandler),
            (r"/[pk]y/attend",AttendHandler),
            (r"/[pk]y/game",GameHandler),
            (r"/[pk]y/gamemore",GamemoreHandler),
            (r"/[pk]y/rank",RankHandler),
            (r"/[pk]y/login",LoginHandler),
            (r"/[pk]y/score",ScoreHandler),
            (r"/[pk]y/org",OrgHandler),
            (r"/[pk]y/point",PointHandler),
            (r"/inter/register",RegisterHandler),
            (r"/logout",LogoutHandler),
            (r"/[pk]y/system",SystemHandler),
            (r"/[pk]y/notify",NotifyHandler),
            (r"/[pk]y/sn",SnHandler),
            (r"/profile",ProfileHandler),
            (r"/auth/login", AuthLoginHandler),
            (r"/auth/logout", AuthLogoutHandler),

        ]
        settings = dict(
            blog_title=u"Tornado Blog",
            #dirname use to get the file path,join means combine 
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            ui_modules={"Entry": EntryModule},
            xsrf_cookies=False,###close this to aviod transfer xsvf to the register 
            #cookie_secret is signed to avoid 
            cookie_secret="11oETzKXQAGaYdkL5gEmGeJJFuYh7EQnp2XdTP1o/Vo=",
            login_url="/auth/login",
            debug = True
        )
        tornado.web.Application.__init__(self, handlers, **settings)
        
        self.cacheRedis = redis.Redis(host=options.redis_host,port=options.redis_port,
                                db=options.redis_db)
        # using redis for
        # Have one global connection to the blog DB across all handlers
        
        self.db = tornado.database.Connection(

            host=options.mysql_host, database=options.mysql_database,
            user=options.mysql_user, password=options.mysql_password)

class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        return self.application.db
    @property
    def cacheRedis(self):
        return self.application.cacheRedis
    
    #justify if user is logined  this is the blog 
    def isLogin(self):
        if self.get_cookie('username') is None:
            self.redirect('/login')
        else:
            post_secret_cookies = self.get_cookie('secret_cookies')
            username = self.get_cookie('username')
            secret_cookies = self.cacheRedis.get('user:username:' + username + ':secret_cookies')
            if post_secret_cookies ==  secret_cookies:
                return username  #
            else:
                self.redirect('/')
    #add user into the group  insert uid into fs_group_mem 
    def add_user_to_group(self,uid,group_id):
        uid = str(uid)
        group_id = str(group_id)
        try:
            self.db.execute("INSERT INTO fs_group_mem (group_id,uid,attendtime) values \
                   (%s,%s,%s)",group_id,uid,str(int(time.time())))  #add the new number 
            #change the cache
            self.db.execute("UPDATE fs_group SET membernum = membernum + 1 WHERE id = %s",group_id)
            if self.cacheRedis.exists('group_user_list:group_id:' + group_id):
                self.cacheRedis.rpush('group_user_list:group_id:' + group_id,uid)
            if self.cacheRedis.exists('mygroup:uid:' + uid):
                self.cacheRedis.lpush('mygroup:uid:' + uid,group_id)
            if self.cacheRedis.exists('group:id:' + group_id):
                self.cacheRedis.hincrby('group:id:' + group_id,'membernum',1)
        except:
            return False
        return True
    def get(self):
        self.isLogin()
   
    def treat_except(self,e):
        is_debug = options.is_debug
        if is_debug: print e 
        else: raise tornado.web.HTTPError(500, "系统开小差了，请重新刷新")



    def get_game_only_level_event(self,gid):
        gid = str(gid)
        eid_list = []
        if not self.cacheRedis.exists('game_only_level:id:' + gid):
            eid_info_list = self.db.query("SELECT eid FROM fs_events WHERE gid=%s",gid)
            for eid_info in eid_info_list:
                eid_list.append(eid_info['eid'])
            self.cacheRedis.set('game_only_level:id:' + gid,eid_list)
        return self.cacheRedis.get('game_only_level:id:' + gid)

    def give_point(self,uid,point_num):
        """ the point_num may have - and + """
        uid = str(uid)
        if self.cacheRedis.exists('users:uid:' + uid):
            self.cacheRedis.hincrby('users:uid:' + uid,'point',point_num)
        self.update_db('fs_users',{'point':point_num},{'uid':uid},'add') 
            

    def incr_game_attend_num(self,eid,incr_num):
        eid = str(eid)
        event_info = self.get_event_info(eid)
        gid = event_info['gid']
        try:
            self.db.execute("UPDATE fs_games_new SET gattend = gattend + %s WHERE gid = %s",incr_num,gid)
            if self.cacheRedis.exists('game:id:' + gid):
                self.cacheRedis.hincrby('game:id:' + gid,'gattend',incr_num)
            self.db.execute("UPDATE fs_events SET eattend = eattend + %s WHERE eid = %s",incr_num,eid)
            if self.cacheRedis.exists('event_info:id:' + eid):
                self.cacheRedis.hincrby('event_info:id:' + eid,'eattend',incr_num)
        except:
            return False
        return True


    def check_event_available(self,eid,new_attend_num):
        """
          check if the attend time has end  or the num is full   first check the time, and second check the max_num_attend
        """
        # game_info = self.get_game_info()
        event_info = self.get_event_info(eid)
        if event_info is False:
            return False
        gacceptend = self.get_game_info(event_info['gid'],['gacceptend','gattend'])['gacceptend']
        if int(time.time()) >  gacceptend:  #this is > > > > 
            return 1 # attend end         
        return 2 if int(event_info['eattend']) + int(new_attend_num) > int(event_info['emaxattend']) and int(event_info['emaxattend']) else True











    def get_event_info(self,eid):
        eid = str(eid)
        if not self.cacheRedis.exists('event_info:id:' + eid):
            try:
                event_info_db = self.db.get("SELECT * FROM fs_events WHERE eid = %s",eid)
                self.cacheRedis.hmset('event_info:id:' + eid,event_info_db)
            except:
                return False
        try:  
            event_info = self.cacheRedis.hgetall('event_info:id:' + eid)
        except:  
            return False
        return event_info

    def get_check_status_name(self,checkstatus,is_group):
        checkstatus = str(checkstatus)
        status_name_dict = {'1':'审核中','2':'attend 成功','3':'attend fail'}
        status_name_dict['0'] = '支付' if is_group  else '未支付'
        return status_name_dict[checkstatus]
        

    def get_user_attend_list(self,uid,field):
        sql = 'SELECT %s FROM fs_user_event WHERE  uid = %s and status=0' % (field,uid)
        try:
            attend_list = self.db.query(sql)
        except:
            return False
        return attend_list


    def justify_user_attend(self,eid,idcard):
        try:
            count = self.db.get('SELECT COUNT(*) AS num FROM fs_user_event WHERE eidcard =%s and eid=%s',idcard,eid)
        except:
            return True #return true then user can not attend
        return True if count['num'] > 0 else False
    def get_full_event_name(self,eid):
        """
          get the event_class event_belong to and glue the classname and event name
        """
        eid = str(eid)
        name_return = ''
        if not self.cacheRedis.exists('event_all_name:id:' + eid):
            try:
                event_info = self.db.get("SELECT upid,ename FROM fs_events WHERE eid = %s",eid)
                name_return += event_info['ename']
                eid_upid_info = self.db.get("SELECT level,upid,name FROM fs_events_class WHERE id = %s",event_info['upid'])
                name_return = eid_upid_info['name'] + '-' + name_return
                if eid_upid_info['level'] == 1:
                    top_level_info = self.db.get("SELECT name FROM fs_events_class WHERE id=%s",eid_upid_info['upid'])
                    name_return = top_level_info['name'] + '-' + name_return
            except:
                return False
            return name_return   


    def addEventMem(self,public_info,mem_info):
        event_info_write = dict(public_info,**mem_info)
        sql = 'INSERT INTO fs_user_event '
        key_str = ''
        value_str = '' 
        for key in event_info_write:
            key_str += key + ','
            event_info_write[key] = ("%s" % event_info_write[key]) #change the str code type
            value_str += '"' + event_info_write[key] + '"' + ','
        key_str = '(' + key_str[0:-1] + ')'
        value_str = '(' + value_str[0:-1] + ')'
        sql += key_str + ' VALUES ' + value_str
        try:
            self.db.execute(sql)
        except:
            return False
        return True


        # self.out(public_info.extend(mem_info))
        # self.out(public_info)
        # self.out(mem_info)

    #get group_list via uid 
    def get_group_list_via_uid(self,uid):
        uid = str(uid)
        list_return = []
        if not self.cacheRedis.exists('mygroup:uid:' + uid):
            group_id_list_db = self.db.query("SELECT group_id FROM fs_group_mem  WHERE uid = %s and is_leader=0",uid)
            for group_id in group_id_list_db:
                self.cacheRedis.lpush('mygroup:uid:' + uid,group_id['group_id']);
                list_return.append(group_id['group_id'])
        list_return = self.cacheRedis.lrange('mygroup:uid:' + uid,0,-1)
        return list_return


    def get_user_who_attend_event(self,eid):
        """
         this method only fetch out head 100 users order by 
        """
        eid = str(eid)
        if not self.cacheRedis.exists("user_attend_event:eid:" + eid):
            uidList = self.db.query("SELECT uid FROM fs_user_event WHERE eid=%s and status=0",eid)
            


    def check_have_attend_by_uid(self,uid,eid):
        """
         if the user(uid) have attend the event, then it will return true else return false
        """
        uid = str(uid)
        eid = str(eid)
        count_info = self.db.get("SELECT COUNT(*) AS num FROM fs_user_event WHERE uid=%s and eid=%s and status=0 and checkstatus = 2",uid,eid)
        return True if count_info['num'] else False


        # self.db.query("SELECT * FROM fs_person_rundata_day")
    def get_recent_run_man(self,eid):
        """
          get the recent 6 users who attend the event 
          each time the process fetch 10 rows rundata from table and check if the user has attend the specific events and if when after check 10 rows data ,we also can not 
          fetch out the 6 recent users, then we should fetch more 10 rows from the table and repeat the operation. 
          and we should also care about the case which there is no more than 6 users attend the event
          this place read list str  from redis and eval to list of python 
        """
        eid = str(eid)
        show_num = 6
        recent_man_list = [] # use list to ensure there is no repeat one 
        jump = 0
        if not self.cacheRedis.exists("recent_run_man:eid:" + eid):
            try:
                while len(recent_man_list) < show_num:
                    user_list = self.db.query("SELECT uid,step_count AS step FROM fs_rundata WHERE status=0 order by id desc limit %s,%s",jump,jump+5)
                    if not user_list:
                        break
                    # self.out(user_list)
                    jump = jump + 5
                    for user_info in user_list:
                        if  user_info not in recent_man_list and self.check_have_attend_by_uid(user_info['uid'],eid):
                            recent_man_list.append(user_info)
                            if len(recent_man_list) == show_num: break
                self.cacheRedis.set("recent_run_man:eid:" + eid,recent_man_list,options.recent_run_man)   
            except:
                return False
        return eval(self.cacheRedis.get("recent_run_man:eid:" + eid))
             

   #justify if already in the group ok the input user is not the leader 
    def alreay_in_group(self,uid,group_id):
        uid = str(uid)
        user_group_list = self.get_group_list_via_uid(uid)
        if group_id in user_group_list:
            return True
        else:
            return False
   # get tag name via tag id 
    def get_tag_info(self,tag_id):
        tag_id = str(tag_id)
        if not self.cacheRedis.exists('tag:id:' + tag_id):
            tag_info = self.db.get("SELECT * FROM fs_tag WHERE id = %s",tag_id)
            self.cacheRedis.set('tag:id:' + tag_id + ':name',tag_info['name'])
        return self.cacheRedis.get('tag:id:' + tag_id + ':name')


   #input a list and add the rank string into the list elment  
    def add_rank_string(self,input_list):
        for index,ele in enumerate(input_list):
            input_list[index]['rank_string'] = '第' + str(index + 1) + '名'
            

   #template output data 
    def return_param(self,result,flag,data,desc):
        return_dict = {'result':result,'flag':flag,'data':data,'desc':desc}
        self.write(return_dict)
   #read group info from cache if not exist then read from mysql and save it to cache 
    def group_info_read(self,group_id):
        group_info = self.cacheRedis.hgetall('group:id:' + group_id)
        if not group_info:#if not in cache 
            group_info = self.db.get('SELECT * FROM fs_group WHERE id = %s',group_id)
            self.cacheRedis.hmset('group:id:' + group_id,group_info) #add info to cache s
        return group_info
   #get userid via tel 
    def get_uid_via_tel(self,tel):
        uid = self.cacheRedis.get('users:tel:' + tel)
        if not uid:# if not in cache read from mysql 
            uid = self.db.get('SELECT uid FROM fs_users WHERE tel = %s LIMIT 1',tel)#read from mysql
            if not uid:
                return False
            uid = uid['uid']
            self.cacheRedis.set('users:tel:' + tel,uid) #write into cache
        return uid

   #get age by idcard 
    def get_age_via_idcard(self,idcard):
        bir_year = int(idcard[6:10])
        now_year = int(time.strftime("%Y",time.localtime()))
        age =  now_year - bir_year
        return age if age > 0 else 0
            

   #get the group_user_list \ input the group_id  and it will return the list of uid in this group 
    def get_group_user_list(self,group_id):
       group_user_list_exists = self.cacheRedis.exists('group_user_list:group_id:' + str(group_id))
       if  not group_user_list_exists:#if not in cache 
           group_user_list = self.db.query('SELECT uid FROM fs_group_mem where group_id = %s',str(group_id))
           if not group_user_list:#if there is no body in the group 
               return []#this is nobody in the group
           for uid_info in group_user_list:
               self.cacheRedis.rpush('group_user_list:group_id:' + str(group_id),uid_info['uid'])
       self.cacheRedis.expire('group_user_list:group_id:' + str(group_id),options.group_user_list_expires)
       group_user_list = self.cacheRedis.lrange('group_user_list:group_id:' + str(group_id), 0,-1)
       return group_user_list  #return the list of the xxx


    #get the userinfo of input param  the search_param may like username user_password etc or a list or a tuple 
    def get_userinfo_via_search_param(self,search_param,uid):
        uid = str(uid)
        if not self.cacheRedis.exists('users:uid:' + uid):# if this user info is not exist then read from mysql and write to cache
            path = options.ipnet
            userinfo = self.db.get("SELECT username,password,tel,idcard,login_times,sex,nickname,CONCAT(%s,avatar) AS avatar,point FROM fs_users WHERE uid = %s",path,uid)
            self.cacheRedis.hmset('users:uid:' + uid,userinfo)
            self.cacheRedis.expire('users:uid:' + uid,options.user_info_expires)
        if isinstance(search_param,str):#if only search one 
            return self.cacheRedis.hget('users:uid:' + uid,search_param) #return string 
        else: #the type of search_param is list 
            user_info = self.cacheRedis.hmget('users:uid:' + uid,search_param) #return list  ['yinnananan', '111111']
            user_info_return = {}
            for index,param in enumerate(search_param):
                user_info_return[param] = user_info[index]
            user_info_return['uid'] = uid
            return user_info_return 

    # def set_user_info(self,uid,param):
    #     """ input type  param is dict"""
    #     uid = str(uid)
    #     if self.cacheRedis.exists('users:uid:' + uid):# if this user info is exist,then change the cache
    #         self.cacheRedis.hmset('users:uid:' + uid,param)
    #     else:
    #         self.update_db('fs_users',param)


    def update_db(self,table,change_param,where,update_type='reset'):
        """the change_param is dict  reset the db info and the default oper is reset and also have add but the add may + or -  """
        try:
            change_sql = "UPDATE %s SET" % (table)
            for key in change_param:
                if update_type == 'reset':
                    change_sql += " %s='%s' and" % (key,change_param[key])
                elif update_type == 'add':
                    change_sql += " %s=%s+%s and" % (key,key,change_param[key])
            change_sql = change_sql[0:-3]
            for key in where:
                change_sql += " WHERE %s=%s and" % (key,where[key])
            change_sql = change_sql[0:-3]
            self.db.execute(change_sql)
        except Exception,e: self.treat_except(e)
        return True








    #sort user by point   
    def sort_by_param(self,list_of_dict,param,reverse=True):
        return sorted(list_of_dict,key=operator.itemgetter(param),reverse=reverse)
        

    def get_current_user(self):
        user_id = self.get_secure_cookie("user")
        if not user_id: return None
        return self.db.get("SELECT * FROM authors WHERE id = %s", int(user_id))


    def createCookies(self):
        str = ''.join(sample('abcdefghijklmnopqrstuvwxyz1234567890^&*()$#@!',8))
        return str
    #send system info 
    def send_sysinfo(self,uid,content,title):
        try:
            self.db.execute("INSERT INTO fs_sysinfo (uid,content,title,time) values (%s,%s,%s,%s)",uid,content,title,str(int(time.time())))
        except:
            return False

    #get group info   return dict 
    def get_group_info(self,group_id):
        group_id = str(group_id)
        group_info = self.cacheRedis.hgetall('group:id:' + group_id)  
        if not group_info:#data not in cache so read from mysql and write into cache 
            group_info = self.db.get("SELECT * FROM fs_group WHERE id = %s",group_id)
            group_info['createtime'] = time.strftime("%Y-%m-%d",time.localtime(group_info['createtime']))
            group_info['tag_name'] = self.get_tag_info(group_info['tag_id'])
            group_info['avatar'] = options.ipnet + group_info['avatar']
            self.cacheRedis.hmset('group:id:' + group_id,group_info) #write into cache
            self.cacheRedis.expire('group:id:' + group_id,options.group_info_expires)
        return group_info

    #get game info  by input param, if param if all,so fetch all param,else fetch the value in input param list 
    def get_game_info(self,game_id,param='all'):
        #save to cache 
        game_id = str(game_id)
        if not self.cacheRedis.exists('game:id:' + game_id):
            game_info = self.db.get("SELECT * FROM fs_games_new WHERE gid=%s",game_id)
            self.cacheRedis.hmset('game:id:' + game_id, game_info)
            self.cacheRedis.expire('game:id:' + game_id,options.game_info_expires)
        game_info_dict = {}
        if param == 'all':
            game_info_dict = self.cacheRedis.hgetall('game:id:' + game_id)
        else:  ####in this place we do not justify the time 
            game_info = self.cacheRedis.hmget('game:id:' + game_id,param)
            for index,value in enumerate(param):
                game_info_dict[value] = game_info[index]
        return game_info_dict


   #justify the game_status?? game start,game end game accept sign  game stop sign start game xxx 
    def make_game_info(self,game_info,uid,param='all'):
        """
          gstatusid  0 game start  1 sign start   2 sign not start   3 sign end    4 game end  
          in this function the attribute of time will be removed 
        """
        game_start = int(game_info['gstarttime'])
        game_end = int(game_info['gendtime'])
        sign_start = int(game_info['gacceptstart'])
        sign_end = int(game_info['gacceptend'])
        nowtime = int(time.time())
        # game_start = 1459085648
        if nowtime > game_end:
             dict_return = {'gstatusid':4,'gstatus':"赛事结束"}
        elif nowtime > game_start:
             dict_return = {'gstatusid':0,'gstatus':'赛事开始'}
        elif nowtime > sign_end:
             dict_return = {'gstatusid':3,'gstatus':'报名结束'}
        elif nowtime > sign_start:
             dict_return = {'gstatusid':1,'gstatus':'接受报名'}
        else:
             dict_return = {'gstatusid':2,'gstatus':'报名未开始'}
        if param != 'all':
            dict_return['gid'] = game_info['gid']
            dict_return['startmap'] = game_info['startmap']
            dict_return['sport_type'] = game_info['sport_type']
            return dict_return

        game_info['gacceptstartdate'] = time.strftime("%Y-%m-%d",time.localtime(sign_start))
        game_info['gacceptenddate'] = time.strftime("%Y-%m-%d",time.localtime(sign_end))
        game_info.pop('gstarttime')
        game_info.pop('gendtime')
        game_info.pop('gacceptstart')
        game_info.pop('gacceptend')
        game_info.pop('gouttime')
        game_info.pop('status')
        game_info.pop('gcheckstatus')
        host = options.ipnet
        game_info['gfrontpage'] = host + game_info['gfrontpage']
        # /py/game?action=game_live&id=' + str(live['id'])
        game_info['agreement'] = host + '/py/game?action=get_agreement&id=' + str(game_info['gid'])
        game_info['gintro'] = host + '/py/game?action=get_intro&id=' + str(game_info['gid']) + \
        '&uid=' + str(uid) + '&gtype=' + str(game_info['gtype_id'])
        game_info['gintro_wecha'] = host + '/ky/game?action=get_intro&id=' + str(game_info['gid']) + \
        '&uid=' + str(uid) + '&gtype=' + str(game_info['gtype_id'])
        game_info.update(dict_return)
        return game_info

  #def debug 
    def out(self,ouput):
        self.write(str(ouput))

   #get game type  zuqiu  paobu 
    def get_game_type(self,type_id='all'): 
       if not self.cacheRedis.exists('gametype'):
           type_info = self.db.query("SELECT * FROM fs_gametype")
           self.cacheRedis.set('gametype',type_info)
       type_info = self.cacheRedis.get('gametype')
       for type_info_ele in eval(type_info):
           if not self.cacheRedis.exists('gametype:id:' + str(type_info_ele['id'])):
               self.cacheRedis.set('gametype:id:' + str(type_info_ele['id']),type_info_ele['name'])
       if type_id == 'all':
           return eval(type_info)
       else:
           return self.cacheRedis.get('gametype:id:' + str(type_id))

    #def get_game_level  if the level_id is 
    def get_game_level(self,level_id='all'):
        if not self.cacheRedis.exists('gamelevel'):
            level_info = self.db.query("SELECT * FROM fs_leveltype")
            self.cacheRedis.set('gamelevel',level_info)
        level_info = self.cacheRedis.get('gamelevel')
        for level_info_ele in eval(level_info):
            if not self.cacheRedis.exists('gamelevel:id:' + str(level_info_ele['id'])):
                self.cacheRedis.set('gamelevel:id:' + str(level_info_ele['id']),level_info_ele['name'])
        if level_id == 'all':
            return eval(level_info)
        else:
            return self.cacheRedis.get('gamelevel:id:' + str(level_id))


class TestHandler(BaseHandler):


    def get(self):
        # print self.update_db('fs_users',{'username':'yinshuai'})
        self.give_point('2',50)



        
    




    def judge_class_have_event(self,class_id,is_group):
        """
          this method is to jduge if there has event under the class, and at first, we should judge the level of the class,and then read data from redis, 
          if there is no data in redis,then  
        """
        pass



class AttendHandler(BaseHandler):
    run_game_not_need_check_type = (2,3) #save the game type  not need pay and dont need check
   
    def get_first_level_filter(self,gid,is_group):
        """
         in this function,we only remove the "class" which has no events! 
        """
        first_level_list = self.get_first_level(gid,is_group)
        if not first_level_list: return []  # if there if nothing in the first level,then return []
        for index_first,info_first in enumerate(first_level_list):
            if int(info_first['is_event']): continue  #if there has event under the current class,then reserve the first_level class
            second_level_list = self.get_second_level(info_first['id'],is_group)
            if not second_level_list:
                del first_level_list[index_first]
                continue
            for index_second,info_second in enumerate(second_level_list):
                if int(info_second['is_event']): break #if there has event under the current second class,then reserve the first_level_class
                else:
                    third_level_list = self.get_third_level(info_second['id'],is_group)
                    if third_level_list: break # if there is no event under the second class,then remove the first level class 
                del first_level_list[index_first]
        return first_level_list

    def get_second_level_filter(self,id,is_group):
        """
           in this function,we only remove the "class" which has no events! and we can make sure that second_level_list is not []
        """
        second_level_list = self.get_second_level(id,is_group)
        for index_second,info_second in enumerate(second_level_list):
            if int(info_second['is_event']): continue
            third_level_list = self.get_third_level(info_second['id'],is_group)
            if not third_level_list: del second_level_list[index_second]
        return second_level_list









    def get_first_level(self,gid,is_group):
        gid = str(gid)
        if int(is_group):
            find_sql = ' and  event_type <> 2'
            redis_key = 'first_level_group:gid:' + gid
        else: 
            find_sql = ' and event_type <> 3'
            redis_key = 'first_level_person:gid:' + gid
        if not self.cacheRedis.exists(redis_key):
            try:
                level1_event_sql = 'SELECT eid AS id,ename AS name,epayfee,group_max,group_min FROM fs_events WHERE gid=%s and status=0 and upid=0 '  % (gid) + find_sql
                level1_event_list = self.db.query(level1_event_sql)
                for index,event in enumerate(level1_event_list):
                    event['is_event'] = 1
                    level1_event_list[index] = event
                level1_class_list =  self.db.query('SELECT id,name FROM fs_events_class WHERE level=0 and status= 0 and gid = %s',gid)
                for index,classInfo in enumerate(level1_class_list):
                    classInfo['is_event'] = 0
                    level1_class_list[index] = classInfo
                first_level_return = level1_event_list + level1_class_list
                self.cacheRedis.set(redis_key,first_level_return)
            except Exception,e: self.treat_except(e)
        try: first_level_return = self.cacheRedis.get(redis_key)
        except Exception,e: self.treat_except(e)
        return eval(first_level_return)

    def get_second_level(self,id,is_group):
        id = str(id)
        if int(is_group):
            find_sql = ' and event_type <> 2'
            redis_key = 'second_level_group:id:' + id
        else:
            find_sql = ' and event_type <> 3'
            redis_key = 'second_level_person:id:' + id 
        if not self.cacheRedis.exists(redis_key):
            try:
                level2_event_sql = 'SELECT eid AS id,ename AS name,epayfee,group_max,group_min FROM fs_events WHERE  status=0 and upid= %s' % (id) + find_sql
                level2_event_list = self.db.query(level2_event_sql)
                for index,event in enumerate(level2_event_list):
                    event['is_event'] = 1
                    level2_event_list[index] = event
                level2_class_list =  self.db.query('SELECT id,name FROM fs_events_class WHERE status=0 and upid = %s',id)
                for index,classInfo in enumerate(level2_class_list):
                    classInfo['is_event'] = 0
                    level2_class_list[index] = classInfo
                second_level_return = level2_event_list + level2_class_list 
                print second_level_return
                self.cacheRedis.set(redis_key,second_level_return)
            except Exception,e: self.treat_except(e)
        try:  second_level_return = self.cacheRedis.get(redis_key)
        except Exception,e:  self.treat_except(e)
        return eval(second_level_return)

    def get_third_level(self,id,is_group):
        id = str(id)
        if int(is_group):
            find_sql = ' and event_type <> 2'
            redis_key = 'third_level_group:id:' + id 
        else:
            find_sql = ' and event_type <> 3' 
            redis_key = 'third_level_person:id:' + id
        if not self.cacheRedis.exists(redis_key):
            try:
                level3_event_sql = 'SELECT eid AS id,ename AS name,epayfee,group_max,group_min FROM fs_events WHERE  status=0 and upid= %s' % (id) + find_sql
                level3_event_list = self.db.query(level3_event_sql)
                for index,eventInfo in enumerate(level3_event_list):
                    eventInfo['is_event'] = 1
                    level3_event_list[index] = eventInfo
                self.cacheRedis.set(redis_key,level3_event_list)
            except Exception,e: self.treat_except(e)
        try: level3_event_list = self.cacheRedis.get(redis_key)
        except Exception,e: self.treat_except(e)
        return eval(level3_event_list)

 
    def get(self):
        action = self.get_argument('action')
        if action == 'get_first_level':
            """ in fact in this place,we also should justify if there is events under the class,and if not have ,then remove the class """
            is_group = self.get_argument('is_group') #justify if it need the group event
            gid = self.get_argument('gid')
            first_level_return = self.get_first_level_filter(gid,is_group)
            self.return_param(1,0,first_level_return,'成功')

        elif action == 'get_second_level':
            is_group = self.get_argument('is_group') #justify if it need the group event
            id = self.get_argument('id')
            second_level_return = self.get_second_level_filter(id,is_group)
            self.return_param(1,0,second_level_return,'成功')

        elif action == 'get_third_level':
            id = self.get_argument('id')
            is_group = self.get_argument('is_group') #justify if it need the group event
            level3_event_list = self.get_third_level(id,is_group)
            self.return_param(1,0,level3_event_list,'成功')

        elif action == 'group_attend':
            group_id = self.get_argument('id')
            eid = self.get_argument('eid')
            gid = self.get_argument('gid')
            leader_name = self.get_argument('leader_name')
            leader_tel = self.get_argument('leader_tel')
            leader_email = self.get_argument('leader_email')
            org_name = self.get_argument('org_name')
            mem_str = self.get_argument('mem_str')
            mem_list = mem_str.split(',')
            available_sign = self.check_event_available(eid,len(mem_list))
            if available_sign is False:
                raise tornado.web.HTTPError(500, "系统开小差了，请重新刷新")
            if available_sign is 1:
                self.return_param(0,201,{},'报名已经结束')
                return 
            if available_sign is 2:
                self.return_param(0,200,{},'该项目报名名额已满')
                return 
            public_info = {'gid':gid,'eid':eid,'group_id':group_id,'org_name':org_name,\
             'leader_name':leader_name,'leader_tel':leader_tel,'leader_email':leader_email}
            epayfee = self.get_event_info(eid)['epayfee']
            game_info = self.get_game_info(gid)
            gtype_id = int(game_info['gtype_id'])
            if not float(epayfee):  public_info['checkstatus'] = 1
            if gtype_id in self.run_game_not_need_check_type: public_info['checkstatus'] = 2
            attendtime = int(time.time()) #all mem use the same attendtime to 
            for uid in mem_list:
                mem_info = self.get_userinfo_via_search_param(['username','tel','avatar','idcard','sex'],uid)
                picPath = mem_info['avatar'][mem_info['avatar'].index('/Uploads'):]
                age = self.get_age_via_idcard(mem_info['idcard'])
                mem_info_write = {'eusername':mem_info['username'],'etel':mem_info['tel'],\
                   'picPath':picPath,'eidcard':mem_info['idcard'],'esex':mem_info['sex'],\
                   'attendtime':attendtime,'eage':age,'uid':uid}
                info = dict(public_info,**mem_info_write)
                result = self.insert_into_db('fs_user_event',info)
                # result = self.addEventMem(public_info,mem_info_write)
                if not result:
                    raise tornado.web.HTTPError(500, "系统开小差了，请重新刷新")
            if not self.incr_game_attend_num(eid,len(mem_list)):
                raise tornado.web.HTTPError(500, "系统开小差了，请重新刷新")
            self.return_param(1,0,{'id':result},'成功')

            # self.checkTheInfo(mem_list)
        elif action == 'checkUserInfo':
            uid = self.get_argument('uid')
            eid = self.get_argument('eid')
            #at first you should justify wheather the user has attend the event 
            search_param = ['sex','idcard','username','tel']
            userInfo = self.get_userinfo_via_search_param(search_param,uid)
            warn_str = ''
            e2cdict = {'sex':'性别','idcard':'身份证号','username':'姓名','tel':'手机号码'}
            for info in userInfo:
                if userInfo[info] == '':
                    warn_str = '用户 ' + e2cdict[info] + ' 没有完善，请提示该用户完善信息' 
                    break;
            if warn_str:
                self.return_param(0,200,{},warn_str)
                return 
            have_attend = self.justify_user_attend(eid,userInfo['idcard'])
            if have_attend:
                self.return_param(0,201,{},'用户已经报名了该项目')
                return 
            self.return_param(1,0,{},'允许')

        elif action == 'get_all_attend':
            uid = self.get_argument('uid') 
            field = 'gid,eid,ueid,eusername,group_id,checkstatus,eage,esex,etel,eidcard'
            user_attend_list = self.get_user_attend_list(uid,field)
            if user_attend_list is False:
                self.return_param(0,500,{},'系统异常')
            else:
                for index,attend_info in enumerate(user_attend_list):
                    user_attend_list[index]['epayfee'] = self.get_event_info(attend_info['eid'])['epayfee']
                    user_attend_list[index]['ename'] = self.get_full_event_name(attend_info['eid'])
                    game_info  = self.get_game_info(attend_info['gid'],['gstarttime','gfrontpage','gname'])
                    user_attend_list[index]['start_time'] = time.strftime("%Y-%m-%d %H:%M",time.localtime(int(game_info['gstarttime'])))
                    user_attend_list[index]['gfrontpage'] =  options.ipnet + game_info['gfrontpage']
                    user_attend_list[index]['gname'] = game_info['gname']
                    user_attend_list[index]['gposition'] = '北京房山'
                    user_attend_list[index]['click_brief'] = options.ipnet + '/py/attend?action=attend_brief&id=' + str(attend_info['ueid'])
                    user_attend_list[index]['agreement'] = options.ipnet + '/py/system?action=get_agreement&gid=' + str(attend_info['gid'])
                    # user_attend_list[index]
                    if attend_info['group_id']:
                        user_attend_list[index]['is_group'] = 1
                        user_attend_list[index]['attend_show'] = self.get_group_info(attend_info['group_id'])['group_name']
                        user_attend_list[index]['status_name'] = self.get_check_status_name(attend_info['checkstatus'],1)
                    else:
                        user_attend_list[index]['attend_show'] = attend_info['eusername']
                        user_attend_list[index]['status_name'] = self.get_check_status_name(attend_info['checkstatus'],0)
            self.return_param(1,0,user_attend_list,'成功')

        elif action == 'attend_brief':
            self.out('this is the brief  in develop')

        elif action == 'person_attend':
            eid = self.get_argument('eid')
            gid = self.get_argument('gid')
            eidcard = self.get_argument('eidcard')
            eusername = self.get_argument('eusername')
            esex = self.get_argument('esex')
            etel = self.get_argument('etel')
            org_name = self.get_argument('org_name')
            uid = self.get_argument('uid')
            age = self.get_age_via_idcard(eidcard)
            if self.justify_user_attend(eid,eidcard):
                self.return_param(0,200,{},'你已经报名了该项目')
                return
            available_sign = self.check_event_available(eid,1)
            if available_sign is False:
                self.return_param(0,500,{},'系统异常')
                return 
            if available_sign is 1:
                self.return_param(0,201,{},'报名结束')
                return 
            if available_sign is 2:
                self.return_param(0,200,{},'该项目报名名额已满')
                return 
            data_write = {'eid':eid,'gid':gid,'eidcard':eidcard,'eusername':eusername,'esex':esex,'etel':etel,'org_name':org_name,'uid':uid,'eage':age,'attendtime':int(time.time())}
            user_avatar = self.get_userinfo_via_search_param(['avatar'],uid)['avatar']
            data_write['picPath'] =   user_avatar[user_avatar.index('/Uploads'):] 
            epayfee = self.get_event_info(eid)['epayfee']
            game_info = self.get_game_info(gid)
            gtype_id = int(game_info['gtype_id'])
            #if the game type if person not need payfee then we set the checkstatus 2 
            if not float(epayfee): data_write['checkstatus'] = 1 # the event is free
            if gtype_id in self.run_game_not_need_check_type: data_write['checkstatus'] = 2 #the type of the game dont need pay and dont need check
            # data_write
            pri_id = self.insert_into_db('fs_user_event',data_write)
            if not pri_id:
                self.return_param(0,500,{},'系统异常')
                return
            if not self.incr_game_attend_num(eid,1):
                self.return_param(0,500,{},'系统异常')
                return
            self.return_param(1,0,{'id':pri_id},'成功')
                
    def insert_into_db(self,table,data_dict):
        key_str = ''
        value_str = ''
        for key in data_dict:
            key_str += key + ','
            data_dict[key] = ("%s" % data_dict[key])
            value_str += '"' + data_dict[key] + '"' + ','
        key_str = ' (' + key_str[:-1] + ') '
        value_str = ' (' +  value_str[:-1] + ') '
        sql = "INSERT INTO %s %s VALUES %s" % (table,key_str,value_str)
        print sql
        try:
            result = self.db.execute(sql)
        except:
            return False
        return result

    def post(self):
        pass
    

class GameHandler(BaseHandler):
    def get_all_game_id(self):
        if not self.cacheRedis.exists('game_id_link'):
            game_id_link = self.db.query("SELECT gid FROM fs_games_new WHERE status = 0")
            for game_info in game_id_link:
                self.cacheRedis.lpush('game_id_link',game_info['gid'])
        return self.cacheRedis.lrange('game_id_link',0,-1)
        # def sort_by_param(self,list_of_dict,param,reverse):
        # return sorted(list_of_dict,key=operator.itemgetter(param),reverse=reverse)
    def get_all_attend_user(self,eid):
        pass
    def get_all_attend_group(self,eid):
        pass

    def get(self):
        action = str(self.get_argument('action'))
        if action == 'front_page':
            uid = self.get_argument('uid',0)
            if int(uid):
                user_info = self.get_userinfo_via_search_param(['login_times'],uid)
            if not int(user_info['login_times']):#first time login then give 50000 point
                self.give_point(uid,50000)

            game_id_link = self.get_all_game_id()
            game_info_list = []
            for gid in game_id_link:
               game_info = self.get_game_info(gid,'all')
               game_info_list.append(self.make_game_info(game_info,uid))
            game_info_return =  self.sort_by_param(game_info_list,'gstatusid',False)
            self.return_param(1,0,game_info_return,'成功')
       
        elif action == 'get_game_info':
            gid = self.get_argument('gid')
            uid = self.get_argument('uid',0) #this place is not need but no time to youhua
            game_info = self.get_game_info(gid,'all')
            game_info = self.make_game_info(game_info,uid,'not all') #just fetch out some param is ok 
            host = options.ipnet
            self.return_param(1,0,game_info,'成功')

        elif action == 'rank_test':
            uidList = self.get_user_attend_event(8)


        elif action == 'get_game_lives':
            gid = str(self.get_argument('gid'))
            if not self.cacheRedis.exists('gamelives:gid:' + gid):
                lives_info_db = self.db.query("SELECT * FROM fs_lives WHERE gid = %s",gid)
                lives_info = []
                for live in lives_info_db:
                    live['time'] = time.strftime("%Y-%m-%d %H:%M",time.localtime(live['time']))
                    live['pic'] = options.ipnet + live['pic']
                    live['content'] = options.ipnet + '/py/game?action=get_live&id=' + str(live['id'])
                    lives_info.append(live)
                self.cacheRedis.set('gamelives:gid:' + gid,lives_info)
                self.cacheRedis.expire('gamelives:gid:' + gid,options.game_lives_expires)
            lives_info = self.cacheRedis.get('gamelives:gid:' + str(gid))
            self.return_param(1,0,eval(lives_info),'成功')

        elif action == 'get_live':
            id = str(self.get_argument('id'))
            if not self.cacheRedis.exists('live_info:id:' + id):
                live_info_db = self.db.get("SELECT content FROM fs_lives WHERE id=%s",id)
                self.cacheRedis.set('live_info:id:' + id,live_info_db['content'])
                self.cacheRedis.expire('live_info:id' + id,options.game_lives_expires)
            live_content = self.cacheRedis.get('live_info:id:' + id)
            self.write(live_content)

        elif action == 'game_score':
            id = str(self.get_argument('id'))
            if not self.cacheRedis.exists('score_info:id:' + id):
                score_info_db = self.db.get("SELECT content FROM fs_scores  WHERE id=%s",id)
                self.cacheRedis.set('score_info:id:' + id,score_info_db['content'])
            score_content = self.cacheRedis.get('score_info:id:' + id)
            self.write(str(score_content))




        elif action == 'get_game_score':
            gid = self.get_argument('gid')
            if not self.cacheRedis.exists('gamescores:gid:' + str(gid)):
                scores_info = []
                scores_info_db = self.db.query("SELECT * FROM fs_scores WHERE gid = %s",str(gid))
                for  score in scores_info_db:
                    score['time'] = time.strftime("%Y-%m-%d %H:%M",time.localtime(score['time']))
                    score['pic'] = options.ipnet + score['pic']
                    score['content'] = options.ipnet + '/py/game?action=game_score&id=' + str(score['id'])
                    scores_info.append(score)
                self.cacheRedis.set('gamescores:gid:' + str(gid),scores_info)
            scores_info = self.cacheRedis.get('gamescores:gid:' + str(gid))
            self.return_param(1,0,eval(scores_info),'成功')

        elif action == 'get_agreement':
            gid = str(self.get_argument('id'))
            if not self.cacheRedis.exists('game_agreement:id:' + gid):
                agreement_info_db = self.db.get('SELECT agreement FROM fs_games_new WHERE gid = %s',gid)
                self.cacheRedis.set('game_agreement:id:' + gid,agreement_info_db['agreement'])
                self.cacheRedis.expire('game_agreement:id:' + gid,options.game_agreement_expires)
            agreement = self.cacheRedis.get('game_agreement:id:' + gid)
            self.write(str(agreement))

        elif action == 'get_intro':
            gid =  self.get_argument('id')
            gtype =  self.get_argument('gtype')
            uid = self.get_argument('uid')

            if gtype == '2': #jianbuzou online personal sport 
                rank_url = options.ipnet + '/py/rank?action=get_person_jbz_run_rank&gid=' + gid + '&uid=' + uid + '&rank_param=day'
                brief_intro_url = options.ipnet + '/py/gamemore?action=get_game_brief&gid=' + gid
                recent_run_man = []
                game_info = self.get_game_info(gid)
                eid = eval(self.get_game_only_level_event(gid))[0]
                if int(game_info['gacceptend']) >  int(time.time()):#when the game is start,but there not consider the end of the game 
                    recent_run_man = self.get_recent_run_man(eid) #in fact the runing game only have one event
                    if recent_run_man is False:
                         raise tornado.web.HTTPError(500, "系统开小差了，请重新刷新")
                    else:
                        for index,user_run_info in enumerate(recent_run_man):
                            user_info = self.get_userinfo_via_search_param(['avatar','nickname'],user_run_info['uid'])
                            recent_run_man[index]['avatar'] = user_info['avatar']
                            recent_run_man[index]['nickname'] = user_info['nickname'] if user_info['nickname'] else '小跑男'
                else: recent_run_man = False #this is the case that the game not start 
                self.render('front' + gid + '.html',recent_run_man=recent_run_man,rank_url=rank_url,brief_intro_url=brief_intro_url)
            elif gtype == '5': #quanyuehui leixing 
                self.render('front' + gid + '.html')
            elif gtype == '4': #mashangpao 
                rank_url = options.ipnet + '/py/rank?action=get_msp_run_rank&gid=' + gid + '&uid=' + uid
                brief_intro_url = options.ipnet + '/py/gamemore?action=get_game_brief&gid=' + gid 
                self.render('front'+gid+'.html',rank_url=rank_url,brief_intro_url=brief_intro_url)
            elif gtype == '3':#jibuzou  online group/personal sport
                game_info = self.get_game_info(gid)
                eid = eval(self.get_game_only_level_event(gid))[0]
                if int(game_info['gacceptend']) >  int(time.time()):#when the game is start,but there not consider the end of the game 
                    recent_run_man = self.get_recent_run_man(eid) #in fact the runing game only have one event
                    if recent_run_man is False:
                         raise tornado.web.HTTPError(500, "系统开小差了，请重新刷新")
                    else:
                        for index,user_run_info in enumerate(recent_run_man):
                            user_info = self.get_userinfo_via_search_param(['avatar','nickname'],user_run_info['uid'])
                            recent_run_man[index]['avatar'] = user_info['avatar']
                            recent_run_man[index]['nickname'] = user_info['nickname'] if user_info['nickname'] else '小跑男'
                else: recent_run_man = False #this is the case that the game not start 
                rank_url = options.ipnet + '/py/rank?action=get_jbz_person_group_rank&gid=' + gid + '&uid=' + uid + '&rank_param=day&attend_type=个人'
                brief_intro_url = options.ipnet + '/py/gamemore?action=get_game_brief&gid=' + gid
                self.render('front'+gid+'.html',rank_url=rank_url,brief_intro_url=brief_intro_url,recent_run_man=recent_run_man)


        elif action == 'get_all_lives':
            if not self.cacheRedis.exists('gamelives_all'):
                lives_info_db = self.db.query("SELECT * FROM fs_lives")
                lives_info = [] 
                for live in lives_info_db:
                    live['time'] = time.strftime("%Y-%m-%d %H:%M",time.localtime(live['time']))
                    live['content'] = options.ipnet + '/py/game?action=get_live&id=' + str(live['id'])
                    live['pic'] = options.ipnet + live['pic']
                    lives_info.append(live)
                self.cacheRedis.set('gamelives_all',lives_info)
                self.cacheRedis.expire('gamelives_all',options.game_lives_all_expires)
            game_lives = self.cacheRedis.get('gamelives_all')
            self.return_param(1,0,eval(game_lives),'成功')



    def post(self):
        self.get_all_game_id()
        # action = self.get_argument
        # print self.get_game_info(1)
        # self.justify_game_status(1,1,1,1)
class RankHandler(BaseHandler):
    type_table = {'day':'fs_person_rundata_day','week':'fs_person_rundata_week','month':'fs_person_rundata_month','quarter':'fs_person_rundata_quarter',\
                   'year':'fs_person_rundata_year'}

    type_group_table = {'day':'fs_group_rundata_day','week':'fs_group_rundata_week','month':'fs_group_rundata_month','quarter':'fs_group_rundata_quarter',\
                   'year':'fs_group_rundata_year'}

    time_local = time.localtime(int(time.time()))
    current_quarter = int(time.strftime("%m",time_local))/3 + 1
    search_param = {'day':time.strftime("%y%m%d",time_local), \
                    'week':time.strftime("%y%U",time_local), \
                    'month':time.strftime("%y%m",time_local),\
                    'quarter':time.strftime("%y",time_local) + str(current_quarter),\
                    'year':time.strftime("%y",time_local)}
    rank_param_e2c = {'day':'日','week':'周','month':'月','quarter':'季','year':'年'}



    def my_rank(self,uid,eid,type): #get the user person rank,make sure the user has attend the game before use this method 
        sql = "SELECT step FROM %s WHERE uid = %s and eid=%s and date='%s'" % (self.type_table[type],uid,eid,self.search_param[type])
        step_info = self.db.get(sql)
        if step_info is None:
            event_info = self.get_event_info(eid)
            return event_info['eattend'] 
        sql2 = "SELECT COUNT(*) AS num FROM %s WHERE eid=%s and step >= %s and date='%s'" % (self.type_table[type],eid,step_info['step'],self.search_param[type])
        my_rank = self.db.get(sql2)
        return my_rank['num']

    def my_group_rank(self,group_id,eid,type):#get the group rank of the man ,make sure the user has attend the game before use this method
        sql = "SELECT step FROM %s WHERE group_id = %s and eid=%s and date='%s'" % (self.type_group_table[type],group_id,eid,self.search_param[type])
        group_step_info = self.db.get(sql)
        if group_step_info is None:
            event_info = self.get_event_info(eid)
            return event_info['eattend']
        sql2 = "SELECT COUNT(*) AS num FROM %s WHERE eid=%s and step >= %s and date='%s'" % (self.type_group_table[type],eid,group_step_info['step'],self.search_param[type])
        my_group_rank = self.db.get(sql2)
        return my_group_rank['num']




    def judge_attend_type(self,uid,eid):
        """
        this method used as (1)judge if user has attend the event (2)if user has attend the event,then judge the attend type(group or personal)
        if the user has not attend,then return false, if the user has attend and the attend type is group,then return the group_id else return 0 
        """
        sql = "SELECT group_id FROM fs_user_event WHERE uid=%s and status=0 and checkstatus=2 and eid=%s" % (uid,eid) 
        try:  attend_info = self.db.get(sql)
        except: return False
        if not attend_info: return -1
        return attend_info['group_id']
              # except Exception,e:
            # print e     

    def get_my_run(self,uid,eid,type):
        """
          use in personal event and get my own rank of all the man,make sure user has attend the event before use this method 
        """
        sql = "SELECT * FROM %s WHERE uid=%s and eid=%s and date=%s" % (self.type_table[type],uid,eid,self.search_param[type])
        run_data = self.db.get(sql)
        avatar = self.get_userinfo_via_search_param(['avatar'],uid)['avatar']
        if run_data is None:#the user not run 
            return {'step':0,'distance':0,'avatar':avatar}
        else:
            run_data['avatar'] = avatar
            run_data['distance'] = round(run_data['distance']/1000.0,1)
        return run_data

    def get_my_group_run(self,group_id,eid,type):
        """
        use in group event and get my group rank of all the groups,make sure user has attend the event before use this method 
        """
        sql = "SELECT * FROM %s WHERE group_id=%s and eid=%s" % (self.type_group_table[type],group_id,eid)
        run_data = self.db.get(sql)
        avatar = self.get_group_info(group_id)['avatar']
        if run_data is None:
            return {'step':0,'distance':0,'avatar':avatar}
        run_data['avatar'] = avatar
        return run_data



    def get_person_popular_list(self,eid,type):#get 100
        """
          return the dict list of the user list 
        """
        eid = str(eid)
        if not self.cacheRedis.exists("person_popular_" + type + ":eid:" + eid):
            sql = "SELECT uid,step FROM %s WHERE eid=%s and date='%s' order by step desc limit 100" % (self.type_table[type],eid,self.search_param[type])
            person_popular_list = self.db.query(sql)
            if not person_popular_list: return []
            self.cacheRedis.set("person_popular_" + type + ":eid:" + eid,person_popular_list,options.rank_data_expires)
        person_popular_list = eval(self.cacheRedis.get('person_popular_' + type + ':eid:' + eid))
        for index,user_popular_info in enumerate(person_popular_list):
            user_info = self.get_userinfo_via_search_param(['avatar','nickname'],user_popular_info['uid'])
            person_popular_list[index]['avatar'] = user_info['avatar']
            person_popular_list[index]['nickname'] = user_info['nickname']
        return person_popular_list #if there is no one run so it will return None

    def get_group_popular_list(self,eid,type): # return the list of the group 
        eid = str(eid)
        if not self.cacheRedis.exists("group_popular_" + type + ":eid" + eid):
            sql = "SELECT group_id,step FROM %s WHERE eid=%s and date='%s' order by step desc limit 100" % (self.type_group_table[type],eid,self.search_param[type])
            group_popular_list = self.db.query(sql)
            if not group_popular_list: return []
            self.cacheRedis.set("group_popular_" + type + ":eid:" + eid,group_popular_list,options.rank_data_expires)
            group_popular_list = eval(self.cacheRedis.get('group_popular_' + type + ':eid:' + eid))
            for index,group_popular_info in enumerate(group_popular_list):
                group_info = self.get_group_info(group_popular_info['group_id'])
                group_popular_list[index]['avatar'] = group_info['avatar']
                group_popular_list[index]['nickname'] = group_info['group_name']
        return group_popular_list #if there is no one run so it will return None

    # def judge_quarter(self,current_time):

    def get(self):
        action = self.get_argument('action')
        rank_param = self.get_argument('rank_param','day')
        uid = self.get_argument('uid')
        gid = self.get_argument('gid')
        eid = eval(self.get_game_only_level_event(gid))[0]
        if action == 'get_person_jbz_run_rank':#runing man online jianbuzou sport
            have_attend = self.check_have_attend_by_uid(uid,eid)
            person_popular_list = self.get_person_popular_list(eid,rank_param)
            if have_attend:
                my_rank = self.my_rank(uid,eid,rank_param)
                my_run = self.get_my_run(uid,eid,rank_param)
                self.render('person_run_rank' + gid + '.html',have_attend=have_attend,person_popular_list=person_popular_list,\
                           my_run=my_run,my_rank=my_rank,rank_param=rank_param,rank_param_e2c = self.rank_param_e2c[rank_param])
            else:
                self.render('person_run_rank' + gid + '.html',have_attend=have_attend,person_popular_list=person_popular_list, \
                             rank_param=rank_param,rank_param_e2c = self.rank_param_e2c[rank_param])
        elif action == 'get_msp_run_rank':#mashangpao 
            self.render('msp_run_rank' + gid + '.html')
        elif action == 'get_jbz_person_group_rank':#jianbuzou group/personal run rank
            """
              one man can only attend one event either group or person, and the man can not change it except for new reposite
            """
            attend_type_get = self.get_argument('attend_type','个人') #param from url
            attend_type = self.judge_attend_type(uid,eid)
            if attend_type is False: raise tornado.web.HTTPError(500, "系统异常")
            if attend_type_get == '个人':
                have_attend = True if attend_type == 0 else False
                my_rank =  self.my_rank(uid,eid,rank_param) if attend_type == 0 else ''
                my_run = self.get_my_run(uid,eid,rank_param) if attend_type == 0 else ''
                person_popular_list = self.get_person_popular_list(eid,rank_param)
                msg = '您还没有参加该项目，或者您参加了该赛事的团队项目'
                self.render('jbz_person_group_rank'+ gid + '.html',have_attend=have_attend,popular_list=person_popular_list,\
                                my_run=my_run,my_rank=my_rank,rank_param=rank_param,attend_type_get=attend_type_get,msg=msg,\
                                rank_param_e2c = '我本' + self.rank_param_e2c[rank_param]
                                )
            else: #the attend_type_get is group
                have_attend = True if attend_type > 0 else False
                my_group_rank = self.my_group_rank(attend_type,eid,rank_param) if attend_type > 0 else ''
                my_group_run  = self.get_my_group_run(attend_type,eid,rank_param) if attend_type > 0 else ''
                group_popular_list = self.get_group_popular_list(eid,rank_param)
                msg = '您还没有参加该项目，或者您参加了该赛事的个人项目'
                self.render('jbz_person_group_rank'+ gid + '.html',have_attend=have_attend,popular_list=group_popular_list,\
                                my_run=my_group_run,my_rank=my_group_rank,rank_param=rank_param,attend_type_get=attend_type_get,msg=msg,\
                                rank_param_e2c = '我的团队本' + self.rank_param_e2c[rank_param])

class SnHandler(BaseHandler):
    def get(self):
        action = self.get_argument('action')
        if action == 'justify_sn_valid':
            id = self.get_argument('id') #attend id   ueid
            uid = self.get_argument('uid') #user id 
            sn = self.get_argument('sn')
            attend_info = self.get_attend_info(id)
            gid = attend_info['gid']
            eid = attend_info['eid']
            is_group = 1 if int(attend_info['group_id']) > 0 else 0
            sn_valid = self.check_sn_valid(sn,eid)
            if sn_valid is False:
                self.return_param(0,500,{},'系统异常')
                return 
            if sn_valid is 1:
                self.return_param(0,200,{},'邀请码已经被使用或者不正确')
                return 
            if sn_valid is 2:
                self.return_param(0,201,{},'邀请码已经过期')
                return
            sn_id = sn_valid['id']  # the sn primary key
            if int(is_group):
                if self.sn_pay_notify_group(id,uid,sn_id) is False:
                    self.return_param(0,202,{},'支付失败')
                    return
            else: # the personal 
                if self.sn_pay_notify_person(id,uid,sn_id) is False:
                    self.return_param(0,202,{},'支付失败')
                    return
            self.return_param(1,0,{},'支付成功')


   
    def get_attend_info(self,id):
        try:
            attend_info = self.db.get("SELECT * FROM fs_user_event WHERE ueid = %s",id)
        except:
            return False 
        return attend_info

    def create_out_trade_num(self): #the out_trade_num is 20
        str_all = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        str_head = time.strftime("%y%m%d%H%M%S",time.localtime(int(time.time())))
        sn_tail = ''.join(sample(str_all,7))
        return str_head + sn_tail
    
    def get_group_attend_mem(self,id):
        """
         the func will return all ueid of the same attendtime 
        """
        attend_info = self.get_attend_info(id)
        if attend_info is False:
            return False
        group_id = attend_info['group_id']
        attendtime = attend_info['attendtime']
        eid = attend_info['eid']
        try:
            ueid_list_db = self.db.query("SELECT ueid FROM fs_user_event WHERE group_id=%s and attendtime=%s and eid=%s",group_id,attendtime,eid)
        except:
            return False
        ueid_list = []
        for ueid_info in ueid_list_db:
            ueid_list.append(str(ueid_info['ueid']))
        return ueid_list



    


    def sn_pay_notify_person(self,id,uid_used,sn_id):
        sn_out_trade_num = self.create_out_trade_num() + '_'
        try:
            self.db.execute("UPDATE fs_user_event SET out_trade_no=%s,checkstatus=1 WHERE ueid=%s",sn_out_trade_num,id)
            self.db.execute("UPDATE fs_invite_sn SET uid_used=%s,is_used=1,use_time=%s WHERE id=%s",uid_used,int(time.time()),sn_id)
        except:
            return False
        return True





    def sn_pay_notify_group(self,id,uid_used,sn_id):
        """
         the input id is the ueid and if the sn is valid ,then there fun is used to creat_order_sn and set the checkstatus as in process
        """
        sn_out_trade_num = self.create_out_trade_num() + '_'
        ueid_list = self.get_group_attend_mem(id)
        ueid_str =  '(' + ','.join(ueid_list) + ')'
        if ueid_list is False:
            return False
        try:
            sql = "UPDATE fs_user_event SET out_trade_no='%s',checkstatus=1 WHERE ueid in %s" % (sn_out_trade_num,ueid_str)
            self.db.execute(sql)
            self.db.execute("UPDATE fs_invite_sn SET uid_used=%s,is_used=1,use_time=%s WHERE id=%s",uid_used,int(time.time()),sn_id)
        except:
            return False 
        return True


    def check_sn_valid(self,sn,eid):
        try:
            user_sn_info = self.db.get("SELECT * FROM fs_invite_sn WHERE sn=%s  and eid=%s and is_used=0 and status=0",sn,eid)
            # self.out(user_sn_info)
            # return
        except:
            return False
        if user_sn_info is None:
            return 1  # the sn is wrong  or it is used 
        expires = user_sn_info['expires']
        if int(time.time()) > expires:
            return 2 #expires 
        return user_sn_info


class ScoreHandler(BaseHandler):
    def get_score_list(self,uid):
        try:
            score_list = self.db.query("SELECT escore,eusername,gid,ueid AS id,eid,group_id FROM fs_user_event WHERE uid = %s and status=0 and escore <> ''",str(uid))
        except:
            return False
        return score_list



    def get(self):
        action = self.get_argument('action')
        if action == 'get_score_list':
            uid = self.get_argument('uid')
            #so there may have user's group score and the personal score ,this all depend on the event type 
            score_list = self.get_score_list(uid)
            if score_list is False:
                self.return_param(0,500,{},'系统异常')
                return 
            for index,score_info in enumerate(score_list):
                game_info = self.get_game_info(score_info['gid'],['gname','gfrontpage'])
                ename = self.get_full_event_name(score_info['eid'])
                if ename == False:
                    self.return_param(0,500,{},'系统异常')
                    return 
                score_list[index]['ename'] = ename
                score_list[index]['gfrontpage'] = options.ipnet + game_info['gfrontpage']
                score_list[index]['gname'] = game_info['gname']
                score_list[index]['escore'] = 'num ' + score_info['escore']
                score_list[index]['score_show_url'] = options.ipnet + '/py/score?action=show_event_score&eid=' + str(score_info['eid'])
                if score_info['group_id']:
                    score_list[index]['is_group'] = 1
                    score_list[index]['attend_info'] = self.get_group_info(score_info['group_id'])['group_name']
                else:
                    score_list[index]['is_group'] = 0
                    score_list[index]['attend_info'] = score_info['eusername']
            self.return_param(1,0,score_list,'成功')

        elif action == 'show_event_score':
            eid = self.get_argument('eid')
            self.out('is in develop yinshuai')

class GamemoreHandler(BaseHandler):

    def get(self):
        action = self.get_argument('action')
        if action == 'get_game_brief':
            gid = self.get_argument('gid')
            self.render('game_brief' + gid + '.html')




class UserHandler(BaseHandler):
    
    def get(self):
        action = self.get_argument('action')
        if action == 'submit_health_data':
            step_count = self.get_argument('step_count')
            flights_climb = self.get_argument('flights_climb')    
            walk_run_distance = self.get_argument('walk_run_distance')
            uid = self.get_argument('uid')
            date = time.strftime("%Y-%m-%d",time.localtime(time.time()))
            today_exist = self.db.get("SELECT COUNT(*) AS sum FROM fs_health WHERE rundate=%s and uid = %s",date,uid)
            if not today_exist['sum']:
                self.write('faf')
                self.db.execute("INSERT INTO fs_health (uid,step_count,flights_climb,walk_run_distance,rundate) values (%s,%s,%s,%s,%s)",uid,step_count,flights_climb,walk_run_distance,date)
            else:
                sql = 'UPDATE fs_health SET step_count=step_count+' + step_count + ',flights_climb=flights_climb+' + flights_climb + ',walk_run_distance = walk_run_distance+' + walk_run_distance ;
                sql = sql + ' WHERE uid=' + uid +  ' and rundate=' + "'" + date + "'" 
                self.db.execute(sql)
            self.return_param(1,0,{},'成功')



    def post(self):
        action = self.get_argument('action')
        if action == 'change_password':
            ori_password = str(self.get_argument('ori_password'))
            new_password = str(self.get_argument('new_password'))
            uid = str(self.get_argument('uid'))
            password = self.get_userinfo_via_search_param('password',uid)
            if ori_password != password:
                self.return_param(0,200,{},'ori password is not right')
                return
            self.db.execute("UPDATE fs_users SET password = %s WHERE uid = %s",new_password,uid)
            if self.cacheRedis.exists('users:uid:' + uid):
                self.cacheRedis.hset('users:uid:' + uid,'password',new_password)
            self.return_param(1,0,{},'成功')




class PointHandler(BaseHandler):


    def get(self):
        action = self.get_argument('action')
        if action == 'get_point_page_url':
            uid = self.get_argument('uid')
            url_app = options.ipnet + '/py/point?action=get_point_page&uid=' + uid
            url_wecha = options.ipnet + '/ky/point?action=get_point_page&uid=' + uid
            return_dict = {'url_app':url_app,'url_wecha':url_wecha}
            self.return_param(1,0,return_dict,'成功')
        elif action == 'get_point_page':
            uid = self.get_argument('uid')
            str_show = "你好id为 %s 的用户，该功能正在开发中" % (uid)
            self.write(str_show)




class GroupHandler(BaseHandler):
    def decr_group_num(self,group_id):
        group_id = str(group_id)
        try:
            self.db.execute("UPDATE fs_group set membernum = membernum -1 where id =%s",group_id) 
            if self.cacheRedis.exists('group:id:' + group_id):
                self.cacheRedis.hincrby('group:id:' + group_id,'membernum',-1)
        except:
            return False
        return True


    def get(self):
         action = str(self.get_argument('action'))
         if action == 'get_group_info':#get the all group info 
             group_id = self.get_argument('id')
             group_info = self.get_group_info(str(group_id))
             self.return_param(1,0,group_info,'成功')#return the data
          
         
         elif action == 'get_tag':
              tag_id = self.get_argument('tag_id')
              self.out(self.get_tag_info(tag_id))


         elif action == 'get_detail_group_info':#get more info include group_mem and group_mem_rank and my rank 
             group_id = self.get_argument('id')
             uid = str(self.get_argument('uid'))
             #get group info 
             group_info = self.get_group_info(str(group_id)) 
             #get all users of the group order by attend time 
             user_list_all = self.get_group_user_list(group_id)
             user_info_all = [] 
             search_param = ['avatar','username','point']
             for uid in user_list_all:
                 user_info_all.append(self.get_userinfo_via_search_param(search_param,uid))
             #get   options.mem_user_show  (default is six )
             user_info_some_return = user_info_all[:int(options.mem_num_show)]
             #get user info order by user point ,fetch  mem_point_show_num
             user_info_point_all_return =  self.sort_by_param(user_info_all,'point',True)
             #add rank string 
             self.add_rank_string(user_info_point_all_return)
             return_dict = {} 
             return_dict['group_info'] = group_info
             return_dict['user_info_some_return'] = user_info_some_return
             return_dict['user_info_point_some_return'] = user_info_point_all_return[:int(options.mem_point_show_num)]
             for user_rank in user_info_point_all_return:
                 if user_rank['uid'] == uid:
                     return_dict['my_rank'] = user_rank
                     break
             self.return_param(1,0,return_dict,'成功')


         elif action == 'get_all_group': #get my group list 
             """
             mygroup:uid:xxx  is the link of the group which i am in but not i created  
             leadergroup:uid:xxx  is the link of the group of my created 
             """
             uid = str(self.get_argument('uid'))
             group_info_return = []  #other man's group  
             leader_group_info_return = [] #the group of me 
             if not self.cacheRedis.exists('mygroup:uid:' + uid):
                group_id_list_db = self.db.query("SELECT group_id FROM fs_group_mem  WHERE uid = %s and is_leader=0",uid)
                for value in group_id_list_db:
                    self.cacheRedis.lpush('mygroup:uid:' + uid,value['group_id'])
             group_id_list = self.cacheRedis.lrange('mygroup:uid:' + uid,0,-1) 
             for group_id in group_id_list:
                 group_info_return.append(self.get_group_info(group_id))

             if not self.cacheRedis.exists('leadergroup:uid:' + uid):
                 group_id_list_db = self.db.query("SELECT group_id FROM fs_group_mem  WHERE uid = %s and is_leader=1",uid)
                 for value in group_id_list_db:
                     self.cacheRedis.lpush('leadergroup:uid:' + uid,value['group_id'])   
             leader_group_id_list = self.cacheRedis.lrange('leadergroup:uid:' + uid,0,-1)
             for group_id in leader_group_id_list:
                 leader_group_info_return.append(self.get_group_info(str(group_id)))

             invite_list = self.db.query("SELECT group_id,id AS invite_id FROM fs_invite WHERE uid = %s",str(uid))
             invite_info_return = []
             for invite_info in invite_list:
                 info_return = self.get_group_info(invite_info['group_id'])
                 info_return['invite_id'] = invite_info['invite_id']
                 invite_info_return.append(info_return)

             # apply_list = self.db.query("SELECT * FROM fs_group_apply WHERE leader_id = %s",uid)
             # apply_list_return = []
             # for apply_info in apply_list:
             #     apply_info_dict = {}
             #     apply_info_dict['id'] = apply_info['id']
             #     apply_info_dict['username'] = self.get_userinfo_via_search_param('username',apply_info['uid'])
             #     group_info = self.get_group_info(apply_info['group_id'])
             #     apply_info_dict['sumrun'] = group_info['sumrun']
             #     apply_info_dict['avatar'] = group_info['avatar']
             #     apply_info_dict['membernum'] = group_info['membernum']
             #     apply_info_dict['group_name'] = group_info['group_name']
             #     apply_info_dict['tag_name'] = group_info['tag_name']
             #     # apply_info_dict['group_name'] = self.group_info_read(str(apply_info['group_id']))['group_name']
             #     apply_info_dict['applytime'] = time.strftime("%Y-%m-%d %H:%M",time.localtime(apply_info['applytime']))
             #     apply_info_dict['excuse'] = apply_info['excuse']
             #     apply_list_return.append(apply_info_dict)

             #return the final result 
             return_dict = {} 
             return_dict['group_info_return'] = group_info_return
             return_dict['leader_group_info_return'] = leader_group_info_return
             return_dict['group_num'] = len(group_info_return) + len(leader_group_info_return)
             return_dict['invite_list_return'] = invite_info_return
             # return_dict['apply_list_return'] = apply_list_return
             self.return_param(1,0,return_dict,'成功')

         elif action == 'get_group_list':
             #read directly from mysql 
             sql = 'SELECT g.createtime,g.id,g.group_name,g.intro,g.membernum,t.name AS tag_name,g.sumrun,g.avatar FROM fs_group AS g left join fs_tag AS t on t.id=g.tag_id'
             all_group_db = self.db.query(sql)
             all_group_return = []
             for  group_info in all_group_db:
                 group_info['createtime'] = time.strftime("%Y-%m-%d %H:%M",time.localtime(group_info['createtime']))
                 group_info['avatar'] = options.ipnet + group_info['avatar']
                 all_group_return.append(group_info)
             self.return_param(1,0,all_group_return,'成功')

         elif action == 'get_group_find':
             find_name = self.get_argument('find_name')
             sql = 'SELECT g.id,g.createtime,g.group_name,g.intro,g.membernum,t.name AS tag_name,g.sumrun,g.avatar FROM fs_group AS g left join fs_tag AS t on t.id=g.tag_id'
             sql = sql + " WHERE g.group_name like '%%" + find_name + "%%'"
             all_group_db = self.db.query(sql)  
             all_group_return = [] 
             for group_info in all_group_db:
                 group_info['createtime'] = time.strftime("%Y-%m-%d %H:%M",time.localtime(group_info['createtime']))
                 group_info['avatar'] = options.ipnet + group_info['avatar']
                 all_group_return.append(group_info)

             self.return_param(1,0,all_group_return,'成功')
             # self.write(sql)



         elif action == 'exit_group':#exit a group (the leader of the group if not you )
             group_id = str(self.get_argument('id'))  #input the group_id     
             uid = str(self.get_argument('uid'))
             #delete from db  and cache
             self.db.execute('DELETE FROM fs_group_mem WHERE uid=%s and group_id=%s',uid,group_id)
             self.cacheRedis.lrem('group_user_list:group_id:' + group_id,uid)
             self.cacheRedis.lrem('mygroup:uid:' + uid,group_id)
             #decr the mem num of the group  
             self.decr_group_num(group_id)
             self.return_param(1,0,{},'成功')

         elif action == 'break_group': #break up a group  you are  the leader of the group 
             group_id = str(self.get_argument('id'))  #get the group_id 
             uid = str(self.get_argument('uid'))
             #delete group data  
             self.db.execute("DELETE FROM fs_group WHERE id = %s",group_id)    
             #delete the leadergroup in cache  
             if self.cacheRedis.exists('leadergroup:uid:' + uid):
                 self.cacheRedis.lrem('leadergroup:uid:' + uid,group_id) #remove data from cache 
             #delete the mem of the group 
             group_uid_list =  self.get_group_user_list(group_id)
             for uid in group_uid_list:
                 self.cacheRedis.lrem('mygroup:uid:' + str(uid),group_id)
             self.cacheRedis.delete('group_user_list:group_id:' + group_id)
             self.db.execute('DELETE FROM fs_group_mem WHERE  group_id = %s',group_id) 
             self.return_param(1,0,{},'成功')

         elif action == 'show_all_members':
             group_id = str(self.get_argument('id'))
             group_user_list = self.get_group_user_list(group_id)
             mem_return = []
             for uid in group_user_list:
                 mem_return.append(self.get_userinfo_via_search_param(['username','avatar'],uid))
             self.return_param(1,0,mem_return,'成功')


         elif action == 'show_all_rank':
             group_id = str(self.get_argument('id'))
             user_list_all = self.get_group_user_list(group_id)
             user_info_all = []
             search_param = ['avatar','username','point']
             for uid in user_list_all:
                 user_info_all.append(self.get_userinfo_via_search_param(search_param,uid))
             #get user info order by user point ,fetch  mem_point_show_num
             user_info_point_return = []
             user_info_point_return =  self.sort_by_param(user_info_all,'point',True)
             #add rank string 
             self.add_rank_string(user_info_point_return)
             self.return_param(1,0,user_info_point_return,'成功')
         else:
             pass  

    def post(self):
          action = self.get_argument('action')
          if action == 'create_group':   #create a new group 
              group_leader_id = str(self.get_argument('uid')) #when create new group the uid is the group_leader_id
              group_name = self.get_argument('group_name')
              group_intro = self.get_argument('group_intro')
              tag_id = self.get_argument('group_tag_id')
              createtime = int(time.time())
              #get user avatar
              # avatar =  self.get_userinfo_via_search_param('avatar',group_leader_id) #user default avatar not user avatar 
              #write mysql 
              result = self.db.execute("INSERT INTO fs_group (group_name,leader_id, intro,tag_id,createtime,membernum) values (%s,%s,%s,%s,%s,%s)",group_name,group_leader_id,group_intro,tag_id,createtime,str(1))
              if result:
                  self.db.execute("INSERT INTO fs_group_mem (group_id,uid,attendtime,is_leader) values \
                   (%s,%s,%s,%s)",str(result),group_leader_id,str(int(time.time())),1)
                  #write redis 
                  # group_info = self.db.get("SELECT * FROM fs_group WHERE id = %s",result)
                  # self.cacheRedis.hmset('group:id:' + str(result),group_info) #save the group info into hash  
                  # self.cacheRedis.expire('group:id:' + str(result),options.group_info_expires)#set the expire time of group_info 
                  self.cacheRedis.lpush('leadergroup:uid:' + group_leader_id,result) #add the new group id into the leader link  
                  self.cacheRedis.expire('leadergroup:uid:' + group_leader_id,options.leadergroup_expires)          
                  self.return_param(1,0,{'id':result},'成功')
              else:
                  self.return_param(0,500,{},'系统异常')


          elif action == 'change_param':
              param = str(self.get_argument('param'))
              group_id = str(self.get_argument('id'))  
              if param == 'groupname':  #change the group name 
                  new_groupname = self.get_argument('new_groupname')
                  try:
                      self.db.execute('UPDATE fs_group set group_name = %s WHERE id=%s',new_groupname,group_id) #modify db 
                      if self.cacheRedis.exists('group:id:' + group_id):
                          self.cacheRedis.hset('group:id:' + group_id,'group_name',new_groupname)
                  except:
                      self.return_param(0,0,{},'failed')
                  self.return_param(1,0,{},'成功')
              elif param == 'group_intro': #change the group intro
                  new_group_intro = self.get_argument('new_group_intro')
                  try:
                      self.db.execute('UPDATE fs_group set intro = %s WHERE id=%s',new_group_intro,group_id) 
                      if self.cacheRedis.exists('group:id:' + group_id):
                          self.cacheRedis.hset('group:id:' + group_id,'intro',new_group_intro)
                  except:
                       self.return_param(0,500,{},'系统异常')
                  self.return_param(1,0,{},'成功')
              else:
                  pass





class InviteHandler(BaseHandler):

    #jduge if group_leader alreay send invite request   return True if the uid already in invite table   
    def judge_alreay_send_invite(self,uid,group_id):
        sql = "SELECT COUNT(*) AS num FROM fs_invite WHERE group_id = " + str(group_id) + " and uid = " + str(uid)
        invite_exist = self.db.get(sql)
        if invite_exist['num']:# if the num is not 0  == 
            return True #the invite exist 
        else:
            return False



    def get(self):
        action = self.get_argument('action')
        if action == 'd':
            pass
          
      
        elif action == 'pass_invite':
            invite_id = self.get_argument('id')
            try:
                invite_info =  self.db.get('SELECT uid,group_id FROM fs_invite WHERE id = %s',invite_id)
                self.db.execute("INSERT INTO fs_group_mem (group_id,uid,attendtime) values (%s,%s,%s)",str(invite_info['group_id']),str(invite_info['uid']),str(int(time.time())))
                #incr the sum number of the group 
                self.db.execute("UPDATE fs_group SET membernum = membernum + 1 WHERE id = %s",str(invite_info['group_id']))
                if self.cacheRedis.exists('group_user_list:group_id:' + str(invite_info['group_id'])):
                    self.cacheRedis.rpush('group_user_list:group_id:' + str(invite_info['group_id']),str(invite_info['uid']))
                if self.cacheRedis.exists('mygroup:uid:' + str(invite_info['uid'])):
                    self.cacheRedis.lpush('mygroup:uid:' + str(invite_info['uid']),str(invite_info['group_id']))
                if self.cacheRedis.exists('group:id:' + str(invite_info['group_id'])):
                    self.cacheRedis.hincrby('group:id:' + str(invite_info['group_id']),'membernum',1)
                group_name = self.get_group_info(str(invite_info['group_id']))['group_name']
                userinfo = self.get_userinfo_via_search_param(['username','tel'],str(invite_info['uid']))
                self.db.execute("DELETE FROM fs_invite WHERE id = %s",str(invite_id))
                username = userinfo['username']
                tel = userinfo['tel']
                content = "(%s)(%s) 已经通过了你的 '%s'团队邀请" % (username,tel,group_name)
                title = '好友通过邀请'
                self.send_sysinfo(str(invite_info['uid']),content,title)

            except:
                self.return_param(0,500,{},'系统异常 ')
            self.return_param(1,0,{},'成功')

        elif action == 'refuse_invite':
            invite_id = self.get_argument('id')
            try:
                self.db.execute("DELETE FROM fs_invite WHERE id = %s",str(invite_id)) 
            except:
                self.return_param(0,500,{},'系统异常 ')
            self.return_param(1,0,{},'成功')
        else:
            pass



    def post(self):
        action = self.get_argument('action')
        if action == 'invite_friends':
            group_id = self.get_argument('id')
            tel = self.get_argument('tel')
            uid = self.get_uid_via_tel(tel)
            if not uid:
                self.return_param(0,200,{},'该用户还没有注册')
                return 
            if self.judge_alreay_send_invite(uid,group_id):
                self.return_param(0,201,{},'邀请已发送，等待对方同意')
                return 
            exist = self.db.get("SELECT COUNT(*) AS num FROM fs_group_mem WHERE uid = %s and group_id=%s",uid,group_id)
            if exist['num']:
                self.return_param(0,202,{},'该用户已经在团队内')
                return 
            self.db.execute("INSERT INTO fs_invite (group_id,uid,invitetime)VALUES (%s,%s,%s)",group_id,uid,str(int(time.time())))
            self.return_param(1,0,{},'成功')

        #the old interface will justify all tel pasted by douhao
        elif action == 'invite_friends_old':
            group_id = self.get_argument('id')
            tel_str = self.get_argument('tel_str')
            self.group_info_read(group_id)#cache group_info
            group_user_list = self.get_group_user_list(group_id)#cache the group_user_list
            tel_list = tel_str.split(',')
            no_register_tel = []
            already_in_group = [] #save the user who already in group 
            waiting_invited = [] #invite has send but no response 
            uid_list = [] #store uid 
            for tel in tel_list:
                uid = self.get_uid_via_tel(tel)
                # self.write(str(uid))
                if not uid: #have man dont register loop all tel 
                    no_register_tel.append(tel)
                else:
                    uid_list.append(uid)
                #if there is no one in the group the group_user_list will return []
                if uid in group_user_list:
                    already_in_group.append(tel) #save the telnum who alreay exist in the group 

                if self.judge_alreay_send_invite(uid,group_id):
                    waiting_invited.append(tel)
            if  no_register_tel:
                self.return_param(0,200,no_register_tel,'some people exist who do not register')
            elif  already_in_group:
                self.return_param(0,201,already_in_group,'some people alreay exist in group')
            elif waiting_invited:
                self.return_param(0,202,waiting_invited,'you have alreay send invite to these man')
            else: # it' time to write mysql 
                sql = 'INSERT INTO fs_invite (group_id,uid,invitetime) VALUES '
                for uid in uid_list:
                    sql = sql + '(' + group_id +  ','+ str(uid) + ',' + str(int(time.time())) + '),'
                sql = sql[:-1] 
                try:
                    result = self.db.execute(sql)
                except:
                    self.return_param(0,500,{},'系统异常')
                    return 

                self.return_param(1,0,{},'成功')  

  
class OrgHandler(BaseHandler):  #yinshuai
    def get(self):
        action = self.get_argument('action')

       
        if action == 'get_org': # search the organizition
            word = self.get_argument('word')
            gid = self.get_argument('gid')
            try:
                sql = "SELECT username AS name FROM fs_org WHERE username LIKE '%%" + word + "%%'"
                org_list = self.db.query(sql)
                self.return_param(1,0,org_list,'成功')
            except:
                self.return_param(0,0,{},'系统异常')
            

class NotifyHandler(BaseHandler):
    """wecha notify """
    def get(self):
        out_trade_no = self.get_argument('out_trade_no')
        print out_trade_no



class ApplyHandler(BaseHandler): #shenqing
    def get(self):
        action = self.get_argument('action')
        if action == 'applyofme': 
            uid = self.get_argument('uid')
            apply_list = self.db.query("SELECT * FROM fs_group_apply WHERE leader_id = %s",str(uid))
            apply_list_return = []
            for apply_info in apply_list:
                 apply_info_dict = {}
                 apply_info_dict['id'] = apply_info['id']
                 apply_info_dict['username'] = self.get_userinfo_via_search_param('username',apply_info['uid'])
                 apply_info_dict['group_name'] = self.group_info_read(str(apply_info['group_id']))['group_name']
                 apply_info_dict['applytime'] = time.strftime("%Y-%m-%d %H:%M",time.localtime(apply_info['applytime']))
                 apply_info_dict['excuse'] = apply_info['excuse']
                 apply_list_return.append(apply_info_dict)
            self.return_param(1,0,apply_list_return,'成功')

        elif action == 'pass_apply':#pass user apply 
             apply_id = self.get_argument('id') #input the id of the param  
             try:#user transaction or not ?? 
                 apply_info = self.db.get("SELECT uid,group_id FROM fs_group_apply WHERE id = %s",apply_id)
                 group_id = str(apply_info['group_id'])
                 uid = str(apply_info['uid'])
                 self.db.execute("INSERT INTO fs_group_mem (group_id,uid,attendtime) values (%s,%s,%s)",group_id,uid,str(int(time.time())))
                 if self.cacheRedis.exists('group_user_list:group_id:' + group_id):
                     self.cacheRedis.rpush('group_user_list:group_id:' + group_id,uid)
                 if self.cacheRedis.exists('mygroup:uid:' + uid):
                     self.cacheRedis.lpush('mygroup:uid:' + uid,group_id)
                 self.db.execute('DELETE FROM fs_group_apply WHERE id = %s',str(apply_id))
             except: 
                 self.return_param(0,500,{},'系统异常')
                 return 
             self.return_param(1,0,{},'成功')

        elif action == 'refuse_apply':#refuse the apply
            apply_id = self.get_argument('id')
            try:
                self.db.execute('DELETE FROM fs_group_apply WHERE id = %s',str(apply_id))
            except:
                self.return_param(0,500,{},'系统异常')
                return
            self.return_param(1,0,{},'成功')
        else:
            pass

    def post(self):
        # send my apply 
        action = self.get_argument('action')
        if action == 'post_apply':
            group_id = self.get_argument('id')
            uid =  self.get_argument('uid')
            leader_id = self.get_group_info(group_id)['leader_id']
            if leader_id == uid:
                self.return_param(0,200,{},'团长不能申请加入自己的团队')
                return
            if self.alreay_in_group(uid,group_id):
                self.return_param(0,201,{},'你已经在该团队中')
                return 
            if self.add_user_to_group(uid,group_id):
                self.return_param(1,0,{},'加入成功')
                return 
            self.return_param(0,500,{},'系统异常')
       
# yinshuai login handler
class LoginHandler(BaseHandler):
      def get(self):
         self.set_secure_cookie('username','yinshuai')
         self.set_secure_cookie('uid','44')
         username = self.get_secure_cookie('username')
         self.write(username)
         self.render('login.html')
      def post(self):
          username = self.get_argument('username')
          inputpassword = self.get_argument('password')
          userid  = self.cacheRedis.get('user:username:' + username + ':userid')
          if userid is None:
              self.write('the user is not exits')
              return
          password = self.cacheRedis.get('user:userid:' + str(userid) + ':password')
          if (inputpassword != password):
              self.write('wrong password')
              return 
          else:
               #write userinfo into cookies 
               secret_cookies = self.createCookies()
               self.cacheRedis.set('user:username:' + username + ':secret_cookies',secret_cookies)
               self.set_cookie('secret_cookies',secret_cookies)
               self.set_cookie('username',username)
               self.redirect('/')



class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_all_cookies()


#register handler
class RegisterHandler(BaseHandler):
      def get(self):
          self.render('register.html')

      def post(self):
           username = self.get_argument('username')
           password = self.get_argument('password')
           repassword = self.get_argument('repassword')
           if password != repassword:
               self.write('please vertify your password')
           else: #write userinfo into redis 
                #judge if the username is already registerd 
                username_exist = self.cacheRedis.get('user:username:' + username + ':userid')
                if username_exist:
                     self.write('this username is exist')
                     return
                globalUserid = self.cacheRedis.get('globalUserid')
                if globalUserid is None:

                      self.cacheRedis.set('globalUserid',1)
                      globalUserid = 1
                else:
                      globalUserid = self.cacheRedis.incr('globalUserid')

                #save the register info 
                self.cacheRedis.set('user:userid:' + str(globalUserid) + ':username',username)
                self.cacheRedis.set('user:userid:' + str(globalUserid) + ':password',password)
                self.cacheRedis.set('user:username:' + username + ':userid',globalUserid)
                #add the new user into the newuserlist,this list only store 10 new user 
                newuser_num = self.cacheRedis.lpush('newuserlist',globalUserid)
                if newuser_num > 10:
                    self.cacheRedis.rpop('newuserlist')

                #when regiser 成功 ,redirect to home 
                self.redirect("/")


class HomeHandler(BaseHandler):
    def get(self):
        username = self.isLogin()
        #get all post of the user 
        userid = self.cacheRedis.get('user:username:' + username + ':userid')
        postlist = self.cacheRedis.lrange('postlink:userid:' + userid,0,-1)
        post_store = []
        for postid in postlist:
            post_info = self.cacheRedis.hgetall('post:postid:' + postid)
            post_store.append(post_info)

        self.write(str(post_store))
            # post_store.append()
    
        self.render('home.html',username=username,post_info=post_store)
      


        """
        entries = self.db.query("SELECT * FROM entries ORDER BY published "
                                "DESC LIMIT 5")
        if not entries:
            self.redirect("/compose")
            return
        self.render("home.html", entries=entries)
        """
    def post(self):
         username = self.isLogin() 
         globalPostid = self.cacheRedis.get('globalPostid')
         if globalPostid is None:
             self.cacheRedis.set('globalPostid',1)
             globalPostid = 1 
         globalPostid = self.cacheRedis.incr('globalPostid')
         post_content = self.get_argument('postContent')
         userid = self.cacheRedis.get('user:username:' + username + ':userid')
         postdata_write = {'username':username,'userid':userid,'post_content':post_content,
                     'current_time':time.ctime()}
         result = self.cacheRedis.hmset('post:postid:' + str(globalPostid),postdata_write)
         if not result:
             self.write('post failed,retry!')
         else:
             #add the user postid into the linklist 
             link_length = self.cacheRedis.lpush('postlink:userid:' + userid,globalPostid)
             if link_length > 5:
                # if the user have lots of post, system will pop some into mongo 
                self.cacheRedis.rpoplpush('postlink:userid:' + userid,'coldlink')
                return
             self.redirect('/')


class SystemHandler(BaseHandler):
    #get system info such as the user has pass you invite 
    
    def get(self):
        action = self.get_argument('action')
        if action == 'get_sysinfo':
            uid = self.get_argument('uid')
            try:
                sysinfo_list = self.db.query("SELECT * FROM fs_sysinfo WHERE uid = %s and status=0",uid)
                for index,sysinfo in enumerate(sysinfo_list):
                    sysinfo['time'] = time.strftime("%Y-%m-%d %H:%M",time.localtime(sysinfo['time']))
                    sysinfo_list[index] = sysinfo
            except:
                self.return_param(0,500,{},'系统异常')
            self.return_param(1,0,sysinfo_list,'成功')

        elif action == 'del_sysinfo':
            id = self.get_argument('id')
            try:
                self.db.execute("DELETE FROM fs_sysinfo WHERE id = %s",id)
            except:
                self.return_param(0,500,{},'系统异常')
            self.return_param(1,0,{},'成功')

        elif action == 'get_ad': #get the picList of the add
            if not self.cacheRedis.exists('ad_pic'):
                try:
                    picList = self.db.query("SELECT * FROM fs_ad")
                    for index,value in enumerate(picList):
                        value['pic'] = options.ipnet + value['pic']
                        picList[index] = value
                    self.cacheRedis.set('ad_pic',picList)
                except:
                    self.return_param(0,500,{},'系统异常')
            picList = self.cacheRedis.get('ad_pic')
            self.return_param(1,0,eval(picList),'成功')

            





       


class ProfileHandler(BaseHandler):
    def get(self):
        userid = self.get_argument('userid')
        username = self.cacheRedis.get('user:userid:' + userid + ':username')
        #fetch his latest 10 posts 
        postlink = self.cacheRedis.lrange('postlink:userid:' + userid,0,10)
        post_store = []
        for postid in postlink:
            post_store.append(self.cacheRedis.hgetall('post:postid:' + postid))
        self.write(str(post_store))

        self.render('profile.html',username=username,postinfo=post_store,userid=userid)




class TagHandler(BaseHandler):
    def get(self):
       if not self.cacheRedis.exists('tag_all'):
           tag_all_db = self.db.query("SELECT * FROM fs_tag")
           host = options.ipnet
           tag_all = []
           for tag in tag_all_db:
               tag['pic'] = host + '/Uploads/TagPic/' + tag['pic']
               tag_all.append(tag)
           self.cacheRedis.set('tag_all',tag_all)
       tag_all = self.cacheRedis.get('tag_all')
       self.return_param(1,0,eval(tag_all),'成功')

    def post(self):
        pass

class ArchiveHandler(BaseHandler):
    def get(self):
        entries = self.db.query("SELECT * FROM entries ORDER BY published "
                                "DESC")
        self.render("archive.html", entries=entries)


class FeedHandler(BaseHandler):
    def get(self):
        entries = self.db.query("SELECT * FROM entries ORDER BY published "
                                "DESC LIMIT 10")
        self.set_header("Content-Type", "application/atom+xml")
        self.render("feed.xml", entries=entries)


class ComposeHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        id = self.get_argument("id", None)
        entry = None
        if id:
            entry = self.db.get("SELECT * FROM entries WHERE id = %s", int(id))
        self.render("compose.html", entry=entry)

    @tornado.web.authenticated
    def post(self):
        id = self.get_argument("id", None)
        title = self.get_argument("title")
        text = self.get_argument("markdown")
        html = markdown.markdown(text)
        if id:
            entry = self.db.get("SELECT * FROM entries WHERE id = %s", int(id))
            if not entry: raise tornado.web.HTTPError(404)
            slug = entry.slug
            self.db.execute(
                "UPDATE entries SET title = %s, markdown = %s, html = %s "
                "WHERE id = %s", title, text, html, int(id))
        else:   
            slug = unicodedata.normalize("NFKD", title).encode(
                "ascii", "ignore")
            slug = re.sub(r"[^\w]+", " ", slug)
            slug = "-".join(slug.lower().strip().split())
            if not slug: slug = "entry"
            while True:
                e = self.db.get("SELECT * FROM entries WHERE slug = %s", slug)
                if not e: break
                slug += "-2"
            self.db.execute(
                "INSERT INTO entries (author_id,title,slug,markdown,html,"
                "published) VALUES (%s,%s,%s,%s,%s,UTC_TIMESTAMP())",
                self.current_user.id, title, slug, text, html)
        self.redirect("/entry/" + slug)


class AuthLoginHandler(BaseHandler, tornado.auth.GoogleMixin):
    @tornado.web.asynchronous
    def get(self):
       
        if self.get_argument("openid.mode", None):
            self.get_authenticated_user(self.async_callback(self._on_auth))
            return
        self.authenticate_redirect()
    
    def _on_auth(self, user):
        if not user:
            raise tornado.web.HTTPError(500, "Google auth failed")
        author = self.db.get("SELECT * FROM authors WHERE email = %s",
                             user["email"])
        if not author:
            # Auto-create first author
            any_author = self.db.get("SELECT * FROM authors LIMIT 1")
            if not any_author:
                author_id = self.db.execute(
                    "INSERT INTO authors (email,name) VALUES (%s,%s)",
                    user["email"], user["name"])
            else:
                self.redirect("/")
                return
        else:
            author_id = author["id"]
        self.set_secure_cookie("user", str(author_id))
        self.redirect(self.get_argument("next", "/"))


class AuthLogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("user")
        self.redirect(self.get_argument("next", "/"))


class EntryModule(tornado.web.UIModule):
    def render(self, entry):
        return self.render_string("modules/entry.html", entry=entry)


def main():
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
