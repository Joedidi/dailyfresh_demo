from django.shortcuts import render, redirect
from django.views.generic import View
from django.urls import reverse
from user.models import User, Address, AddressManager
import re
from django.contrib import messages
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from django.conf import settings
from django.http import HttpResponse
from django.core.mail import send_mail
from celery_tasks.tasks import send_register_active_email
from django.contrib.auth import authenticate, login, logout
from utils.mixin import LoginRequiredMixin
from goods.models import GoodsSKU
from order.models import OrderInfo, OrderGoods
from django_redis import get_redis_connection
from django.core.paginator import Paginator


# Create your views here.

def register(request):
    """
    显示注册页面
    :param request:
    :return:
    """
    if request.method == "GET":
        return render(request, 'register.html')
    elif request.method == 'POST':
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        # 进行校验
        if not all([username, password, email]):
            # 数据不完整
            messages.success(request, '数据不完整')
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        if allow != 'on':
            messages.success(request, '请同意协议')
            return render(request, 'register.html', {'errmsg': '请同意协议'})

        # user = User()
        # user.username = username
        # user.password = password
        # user.email = email
        #
        # user.save()
        # 校验用户名是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在
            user = None
        if user:
            messages.success(request, '用户已经存在啦')
            return render(request, 'register.html')
        user = User.objects.create_user(username, email=email, password=password)
        user.is_active = 0
        user.save()

        # 返回应答，跳转首页

        return redirect(reverse('goods:index'))
    else:
        print('错误')


# /user/register
class RegisterView(View):
    """注册"""

    def get(self, request):
        """显示注册页面"""
        return render(request, 'register.html')

    def post(self, request):
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        # 进行校验
        if not all([username, password, email]):
            # 数据不完整
            messages.success(request, '数据不完整')
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        if allow != 'on':
            messages.success(request, '请同意协议')
            return render(request, 'register.html', {'errmsg': '请同意协议'})

        # user = User()
        # user.username = username
        # user.password = password
        # user.email = email
        #
        # user.save()
        # 校验用户名是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 用户名不存在
            user = None
        if user:
            messages.success(request, '用户已经存在啦')
            return render(request, 'register.html')
        user = User.objects.create_user(username, password=password, email=email)
        user.is_active = 0
        user.save()
        # 发送激活邮件，包含激活链接：/user/active/username
        # 激活链接中需要包含用户的身份信息，并且需要加密 itsdangerous

        # 加密用户的身份信息，生成激活token
        serializer = Serializer(settings.SECRET_KEY, 3600)
        info = {'confirm': user.id}
        token = serializer.dumps(info)
        token = token.decode()
        # 发邮件
        # subject = '天天生鲜欢迎信息'
        # message = ''
        # html_message = '<h1>{0}, 欢迎您成为天天生鲜注册会员</h1>请点击下面链接激活您的账户<br/><a href="http://127.0.0.1:8000/user/active/{1}">http://127.0.0.1/user/active/{2}</a>'.format(username, token, token)
        # sender = settings.EMAIL_FROM
        # receiver = [email]
        #
        # send_mail(subject=subject,message = message,from_email=sender,recipient_list=receiver,html_message=html_message)
        # 用task发邮件
        send_register_active_email.delay(email, username, token)

        # # 返回应答，跳转首页
        return redirect(reverse('goods:index'))


class ActiveView(View):
    """用户激活"""

    def get(self, request, token):
        """进行用户激活"""
        # 进行解密，获取用户信息
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            user_id = info['confirm']
            # 根据ID获取用户信息
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()
            # 返回到登录页面
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            # 激活链接已过期
            return HttpResponse('激活链接已过期')


class LoginView(View):
    '''登录页面'''

    def get(self, request):
        # 判断是否记住用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''
        # 使用模板
        return render(request, 'login.html', {'username': username, 'checked': checked})

    def post(self, request):
        # 接收数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')

        # 校验数据
        if not all([username, password]):
            messages.success(request, '数据不完整')
            return render(request, 'login.html', {'errmsg': '数据不完整'})

        # 业务处理: 登录校验
        user = authenticate(username=username, password=password)

        if user is not None:
            # 用户名正确
            if user.is_active:
                # 用户已激活
                # 记录用户的登录状态

                login(request, user)
                # 获取要跳转的地址, 默认跳转到首页
                next_url = request.GET.get('next', reverse('goods:index'))
                # 跳转到首页
                response = redirect(next_url)
                remember = request.POST.get('remember')

                if remember == 'on':
                    # 记住用户名
                    response.set_cookie('username', username, max_age=7 * 24 * 3600)
                else:
                    # 删除用户名
                    response.delete_cookie('username')
                return response
            else:
                # 用户未激活
                messages.success(request, '账户未激活')
                return render(request, 'login.html', {'errmsg': '账户未激活'})
        else:
            # 用户名密码错误
            messages.success(request, '用户名或密码错误')
            return render(request, 'login.html', {'errmsg': '用户名或密码错误'})

        # 返回应答


class LogoutView(View):
    """退出登录"""

    def get(self, request):
        """退出登录"""
        # 清除用户的session信息
        logout(request)

        # 跳回首页
        return redirect(reverse('goods:index'))


# /user
class UserInfoView(LoginRequiredMixin, View):
    """用户中心——信息页"""

    def get(self, request):
        '''显示用户信息页面'''
        # page = 'user
        # request.user
        # 如果用户未登录-》AninymousUser类的实例
        # 如果登录-》User类的一个实例
        # request.user.is_authenticated()

        # 获取个人信息
        user = request.user
        address = Address.objects.get_default_address(user)

        '''
        获取redis连接1
        from redis import StrictRedis
        sr =  StrictRedis(host= '',port='',db=9)
        '''

        con = get_redis_connection('default')  #获取redis连接2

        history_key = 'history_{0}'.format(user.id)

        # 获取用户最新浏览的5条商品记录
        sku_ids = con.lrange(history_key, 0, 4)

        goods_list = []
        for i in sku_ids:
            goods = GoodsSKU.objects.get(id=i)
            goods_list.append(goods)

        # 组织上下文
        context = {
            'page': 'user',
            'user': user,
            'address': address,
            'goods_list': goods_list,
        }
        print(context)
        # 如果用户已登录 request.user.is_authenticated 返回True，在模板变量中可以直接用 user.is_authenticated
        return render(request, 'user_center_info.html', context)


# /user/order
class UserOrderView(LoginRequiredMixin, View):
    """用户中心——订单页"""

    def get(self, request, page):
        '''显示订单页面'''
        # 获取登录对象
        user = request.user

        # 获取用户的订单信息
        orders = OrderInfo.objects.filter(user=user)

        # 遍历获取订单的商品信息
        for order in orders:
            order_skus = OrderGoods.objects.filter(order_id=order.order_id)

            # 计算小计
            for order_sku in order_skus:
                amount = order_sku.price * order_sku.count

                # 动态加属性
                order_sku.amount = amount

            # 动态加属性
            order.order_skus = order_skus
            order.status_name = OrderInfo.ORDER_STATUS[str(order.order_status)]

        # 分页
        paginator = Paginator(orders, 2)

        # 获取第page页的对象s
        try:
            page = int(page)
        except Exception as e:
            page = 1
        order_page = paginator.page(page)

        '''
        object_list 当前页的对象列表
        has_next() 有无下一页
        has_ previous() 有无上一页
        has_other_pages() 有无其他页
        next_page_number() 下一页页码
        previous_page_number() 上一页页码
        start_index() 返回当前页第一个对象的在所有对象中的索引，注意，从1开始
        end_index() 返回当前页最后一个对象在所有对象中的索引，注意，从1开始
        paginator 所关联的Paginator对象

        '''

        # todo: 进行页码控制， 页面上最多显示5个页面
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        # 组织上下问
        context = {
            'order_page': order_page,
            'pages': pages,
            'page': 'order',
        }

        return render(request, 'user_center_order.html', context)


# /user/address
class UserSiteView(LoginRequiredMixin, View):
    """用户中心——地址页"""

    def get(self, request):
        '''显示地址页面'''
        # 获取登录对象
        user = request.user
        # # 获取用户默认收货地址
        # try :
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist as e:
        #     address = None
        address = Address.objects.get_default_address(user)

        # 使用模板
        return render(request, 'user_center_site.html', {'address': address, 'user': user})

    def post(self, request):
        """地址的添加"""
        # 接收数据
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')

        # 校验数据
        if not all([receiver, addr, phone]):
            messages.success(request, '数据不完整')
            return render(request, 'user_center_site.html', {'errmsg': '数据不完整'})

        if not re.match(r'^1[3|4|5|7|8][0-9]{9}$', phone):
            messages.success(request, '手机格式错误')
            return render(request, 'user_center_site.html', {'errmsg': '手机格式错误'})

        if not re.match(r'^[1-9]{6}$', zip_code):
            messages.success(request, '邮政编码错误')
            return render(request, 'user_center_site.html', {'errmsg': '邮政编码错误'})

        # 业务处理： 地址添加

        user = request.user
        # try :
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist as e:
        #     address = None
        address = Address.objects.get_default_address(user)
        if address:
            is_default = False
        else:
            is_default = True

        Address.objects.create(user=user, receiver=receiver, addr=addr, zip_code=zip_code, phone=phone,
                               is_default=is_default)

        # 返回应答
        return redirect(reverse('user:address'))
