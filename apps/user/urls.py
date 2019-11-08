#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
@author: Jamin Chen
@date:  2019/10/31 11:23
@explain: 
@file: urls.py
"""
from django.contrib.auth.decorators import login_required
from django.urls import path,re_path
from user.views import RegisterView,ActiveView,LoginView,LogoutView,UserInfoView,UserSiteView,UserOrderView


urlpatterns = [
    # path('register/', views.register, name='register'),
    # path('register_handle', views.register_handle, name='register_handle'),
    path('register', RegisterView.as_view(), name='register'),  # 注册
    re_path('active/(?P<token>.*)', ActiveView.as_view(), name='active'),  # 用户激活
    path('login', LoginView.as_view(), name='login'),  # 登录
    path('logout', LogoutView.as_view(), name='logout'),  # 退出登录

    # path('', login_required(UserInfoView.as_view()), name='user'),  # 用户信息
    # path('order/', login_required(UserOrderView.as_view()), name='order'),  # 订单
    # path('address/', login_required(UserSiteView.as_view()), name='address'),  # 地址

    # 使用LoginRequiredMixin装饰器
    path('', UserInfoView.as_view(), name='user'),  # 用户信息
    re_path('order/(?P<page>\d+)/', UserOrderView.as_view(), name='order'),  # 订单
    path('address/', UserSiteView.as_view(), name='address'),  # 地址
]
