import re

path = 'backend/services/text_cleaner.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

start = content.find('    # 格式符 OCR 错误（字符串内 $ \u2192 %）')
end = content.find('\n    # 操作符中 $ 误识别为 %')

if start == -1 or end == -1:
    print('markers not found', start, end)
    exit(1)

new_block = (
    '    # 格式符 OCR 错误（字符串内 $ \u2192 %）\n'
    "    (r'\\$d', '%d'),\n"
    "    (r'\\$s', '%s'),\n"
    "    (r'\\$f', '%f'),\n"
    "    (r'\\$c', '%c'),\n"
    "    (r'\\$lf', '%lf'),\n"
    "    (r'\\$ld', '%ld'),\n"
    '    # 格式符前缀 t 误识别\n'
    "    (r'\\btd\\b', '%d'),\n"
    "    (r'\\bta\\b', '%d'),\n"
    "    (r'\\btlf\\b', '%lf'),\n"
    "    (r'\\btf\\b', '%f'),\n"
    "    (r'\\btc\\b', '%c'),\n"
    "    (r'\\bts\\b', '%s'),\n"
    "    (r'#td', '%d'),\n"
    "    (r'#ta', '%d')"
)

new_content = content[:start] + new_block + content[end:]
with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)
print('done, length:', len(new_content))

# verify rule works
test = 'printf("Enter $d numbers;", n);'
for pattern, repl in [
    (r'\$d', '%d'),
    (r'\$s', '%s'),
]:
    test = re.sub(pattern, repl, test)
print('test result:', test)
