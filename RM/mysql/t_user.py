# -*- coding: UTF-8 -*-
import logging
from .connector import Connection

# ------------------------------------
#          user表增删改查逻辑
# ------------------------------------
# 注：仅可由命令逻辑调用，默认参数均为合法
#     此处不得增删user表，要增删的话，需直接修改数据库
#     不进行commit操作
#     仅提供修改pages的接口

def search(user_id:str='', name:str='', phone:str='', only_reviewer:bool=False) -> dict:
    ''' 根据{user_id}、{name}、{phone}以及是否为审核人模糊搜索user表内容。

    Args:
        user_id(str): 用户ID（可选/默认值空）
        name(str): 用户姓名（可选/默认值空）
        phone(str): 用户手机（可选/默认值空）
        only_reviewer: 只搜索审核人（可选/默认值False）

    Returns:
        {"user": [(id, name, phone, role, status), ...]}

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'user_id': user_id, 'name': name, 'phone': phone, 'only_reviewer': only_reviewer}))
    assert type(user_id) == str, 'invalid arg: user_id'
    assert type(name) == str, 'invalid arg: name'
    assert type(phone) == str, 'invalid arg: phone'

    ret = {'user': []}
    with Connection() as (cnx, cursor):
        if only_reviewer:
            cursor.execute('''
                SELECT id, name, phone, role, status
                FROM user
                WHERE available = 1 AND role = 1 AND id LIKE %s AND name LIKE %s AND phone LIKE %s
                ''', ('%{}%'.format(user_id), '%{}%'.format(name), '%{}%'.format(phone))
            )
            logger.debug(cursor.statement)
            cnx.commit()
        else:
            cursor.execute('''
                SELECT id, name, phone, role, status
                FROM user
                WHERE available = 1 AND id LIKE %s AND name LIKE %s AND phone LIKE %s
                ''', ('%{}%'.format(user_id), '%{}%'.format(name), '%{}%'.format(phone))
            )
            logger.debug(cursor.statement)
            cnx.commit()
        ret['user'] = cursor.fetchall()

    logger.debug('return: {}'.format(ret))
    return ret


def fetch(user_id:str) -> tuple:
    ''' 按照user_id获取user表内容。

    Args:
        user_id(str): 用户ID

    Returns:
        (id, name, phone, role, status)

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'user_id': user_id}))
    assert type(user_id) == str, 'invalid arg: user_id'

    with Connection() as (cnx, cursor):
        cursor.execute('''
            SELECT id, name, phone, role, status
            FROM user
            WHERE id = %s
            ''', (user_id,)
        )
        logger.debug(cursor.statement)
        cnx.commit()
        row = cursor.fetchone()

    logger.debug('return: {}'.format(row))
    return row


def __contains__(user_id:str, only_reviewer:bool=False) -> bool:
    ''' 检查user表中是否存在{user_id}，可设置是否仅搜索审核人。

    Args:
        user_id(str): 用户ID
        only_reviewer: 只搜索审核人（可选/默认值False）

    Returns:
        bool: {user_id}存在返回True，否则返回False

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'user_id': user_id, 'only_reviewer': only_reviewer}))
    assert type(user_id) == str, 'invalid arg: user_id'
    
    with Connection() as (cnx, cursor):
        if only_reviewer:
            cursor.execute(
                "SELECT 1 FROM user WHERE available = 1 AND role = 1 AND id = %s", (user_id,)
            )
            logger.debug(cursor.statement)
            cnx.commit()
        else:
            cursor.execute(
                "SELECT 1 FROM user WHERE available = 1 AND id = %s", (user_id,)
            )
            logger.debug(cursor.statement)
            cnx.commit()
        row = cursor.fetchone()
    
    logger.debug('return: {}'.format(bool(row)))
    return bool(row)


def pop(count:int=1, excludes:list=None, urgent:bool=False, hide_busy:bool=True) -> list:
    ''' 获取下{count}个审核人。

    根据条件获取下{count}个审核人。获取时排除{excludes}中的审核人ID，如果设置了urgent，则额外排除status=1的审核人。

    Args:
        count(int): 需要获取的审核人数量（可选/默认值1）；
        excludes(list): 排除的审核人ID（可选/默认值[]）；
        urgent(bool): 是否排除status=1及status=2（可选/默认值False）；
        hide_busy(bool): 是否隐藏status=2（可选/默认值True）；

    Returns:
        [(id, name, phone, role, status, pages_diff, current), ...]：长度为{count}的审核人ID元组列表，每个元组包括用户信息和当前报告数量（长度不超过审核人总数）

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'count': count, 'excludes': excludes, 'urgent': urgent, 'hide_busy': hide_busy}))
    assert type(count) == int, 'invalid arg: count'
    if not excludes:
        excludes = []
    assert type(excludes) == list, 'invalid arg: excludes'

    selectResults = []
    with Connection() as (cnx, cursor):
        # 选择审核人，按工作量（当前报告、当前页数）排序
        cursor.execute('''
            SELECT id, name, phone, role, IF(
                    id = (
                        SELECT latest_history.reviewerid
                        FROM (SELECT reviewerid, end FROM history ORDER BY id DESC LIMIT 1) AS latest_history
                        WHERE NOT EXISTS (SELECT 1 FROM current WHERE current.start > latest_history.end AND current.reviewerid != '')
                    ), -1, status
                ) AS status, (
                    pages - (SELECT MIN(pages) AS min_pages FROM user WHERE user.available = 1 AND user.role = 1)
                ) AS pages_diff, IFNULL(current, 0) AS current
            FROM user LEFT JOIN (
                    SELECT reviewerid, COUNT(1) AS current
                    FROM current
                    GROUP BY reviewerid 
                ) AS temp_count ON user.id = temp_count.reviewerid
            WHERE available = 1 AND role = 1
            ORDER BY current, pages_diff
        ''')
        logger.debug(cursor.statement)
        cnx.commit()
        selectResults = cursor.fetchall()

    selectResults = [item for item in selectResults if item[0] not in excludes]
    if urgent:
        # 提升status=0(空闲)的审核人优先级
        selectResults = [item for item in selectResults if item[4] == 0] + [item for item in selectResults if item[4] != 0]
    if hide_busy:
        # 仅筛选列表中status=0和status=1的审核人
        selectResults = [item for item in selectResults if item[4] == 0 or item[4] == 1]

    logger.debug('return: {}'.format(selectResults[0:count]))
    return selectResults[0:count]


def set_status(user_id:str, status:int):
    ''' 设置忙碌状态status。

    Args:
        user_id(str): 用户ID
        status(int): 状态

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'user_id': user_id, 'status': status}))
    assert __contains__(user_id), 'invalid arg: user_id'
    assert status in [0, 1, 2], 'invalid arg: status'

    with Connection() as (cnx, cursor):
        cursor.execute('''
            UPDATE user
            SET status = %s, status_since = NOW() 
            WHERE id = %s
            ''', (status, user_id)
        )
        logger.debug(cursor.statement)
        cnx.commit()


def reset_status(days:int=7):
    ''' 重置超时(超过{days})的忙碌状态status。

    Args:
        days(int): 超时时间

    Raises:
        AssertionError: 如果参数类型非法
    '''
    logger = logging.getLogger(__name__)
    logger.debug('args: {}'.format({'days': days}))
    assert type(days) == int, 'invalid arg: days'

    with Connection() as (cnx, cursor):
        cursor.execute('''
            UPDATE user
            SET status = 0, status_since = NOW() 
            WHERE status != 0 AND DATEDIFF(NOW(), status_since) >= %s
            ''', (days,)
        )
        logger.debug(cursor.statement)
        cnx.commit()
