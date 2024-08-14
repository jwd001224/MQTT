# import os
#
# import pandas as pd
# import qrcode
#
# # 读取 Excel 文件
# file_path = '出厂编号.xlsx'  # 替换为你的文件路径
# df = pd.read_excel(file_path, sheet_name='团风', usecols=[0, 3], names=['FirstColumn', 'FourthColumn'])  # 使用工作表名称
#
# # 创建 QRcode 目录
# if not os.path.exists('QRcode'):
#     os.makedirs('QRcode')
#
# for index, row in df.iterrows():
#     # 获取第一列的值
#     data = row['FirstColumn']
#     for i in range(1, 3):
#         qr_data = f"https://cdn-evone-oss.echargenet.com/IntentServe/index.html?M&qrcode=gwwl//:1031:1.0.0:3:{data}:FFFFFFFFFFFF:00{i}"
#
#         # 创建二维码
#         qr = qrcode.QRCode(
#             version=8,
#             error_correction=qrcode.constants.ERROR_CORRECT_L,
#             box_size=15,
#             border=2,
#         )
#         qr.add_data(qr_data)
#         qr.make(fit=True)
#
#         # 生成二维码图片
#         img = qr.make_image(fill='black', back_color='white')
#
#         # 获取第四列的字符串并创建目录
#         folder_name = row['FourthColumn']
#         folder_path = os.path.join('QRcode', folder_name)
#         if not os.path.exists(folder_path):
#             os.makedirs(folder_path)
#
#         # 保存二维码图片
#         img_path = os.path.join(folder_path, f'枪{i}.png')
#         img.save(img_path)
#
#         print(f'二维码已保存到: {img_path}')
#


start_test = 1031240801010001
stop_test = 1031240801010230

for i in range(start_test, stop_test + 1):
    print(i)
