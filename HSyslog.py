import inspect
import os
import platform
import logging.handlers
import gzip
import shutil

# 获取当前系统类型
system_type = platform.system()

# 根据系统类型选择日志记录模块
if system_type == 'Linux':
    import syslog
else:
    import logging

# 设置日志格式
log_format = '%(asctime)s - %(levelname)s - %(message)s'
log_formatter = logging.Formatter(log_format)

# 创建日志记录器
if system_type == 'Linux':
    syslog.openlog(ident='my_program', facility=syslog.LOG_LOCAL0)
else:
    logging.basicConfig(level=logging.INFO, format=log_format)

# 创建文件处理器
log_filename = "/opt/hhd/LOG/HCLOG.log"
log_directory = "/opt/hhd/LOG"
log_max_size = 3 * 1024 * 1024  # 3MB
count = 1

if not os.path.exists(log_directory):
    os.makedirs(log_directory)
else:
    pass

if system_type == 'Linux':
    file_handler = logging.handlers.RotatingFileHandler(log_filename, maxBytes=log_max_size, backupCount=10)
else:
    file_handler = logging.handlers.RotatingFileHandler(log_filename, mode='a', maxBytes=log_max_size,
                                                        backupCount=10)
file_handler.setFormatter(log_formatter)

# 将处理器添加到日志记录器
if system_type == 'Linux':
    syslog_logger = logging.getLogger('my_program')
    syslog_logger.setLevel(logging.INFO)
    syslog_logger.addHandler(file_handler)
else:
    logging.getLogger().addHandler(file_handler)

# 测试日志记录
logger = syslog_logger if system_type == 'Linux' else logging.getLogger()


# 检查日志文件大小，超过限制则压缩并创建新文件
def check_log_size(log_filename, max_size):
    global count
    if os.path.getsize(log_filename) > max_size:
        with open(log_filename, 'rb') as f_in, gzip.open(log_filename + str(count) + '.gz', 'wb') as f_out:
            count += 1
            f_out.writelines(f_in)
        os.remove(log_filename)
        logger.info('Log file has been compressed and rotated.')


def log_info(msg):
    try:
        logger.info(msg)
        check_log_size(log_filename, log_max_size)
    except Exception as e:
        print(f"\033[91m{e} .{inspect.currentframe().f_lineno}\033[0m")
        print(f"\033[91m date_msg: {msg}\033[0m")

