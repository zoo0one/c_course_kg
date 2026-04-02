"""
PDF 文字清洗管道 — C 语言教材专项
10 步清洗流程：编码标准化 → 页眉页脚 → 目录 → 断行修复
          → 代码块保护 → OCR纠错 → 章节识别 → 噪声过滤
          → 段落重组 → 关键词标注
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


# ─────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────

@dataclass
class Segment:
    """一个清洗后的段落/章节块"""
    section_id: str = ""
    title: str = ""
    text: str = ""
    keywords: List[str] = field(default_factory=list)
    has_code: bool = False
    char_count: int = 0
    level: int = 0          # 标题层级 1/2/3


@dataclass
class CleanResult:
    raw_chars: int = 0
    clean_chars: int = 0
    chapters_detected: int = 0
    has_code_blocks: bool = False
    segments: List[Segment] = field(default_factory=list)
    clean_text: str = ""   # 完整清洗后文本（供快速预览）


# ─────────────────────────────────────────────
# C 语言关键词词典
# ─────────────────────────────────────────────

C_KEYWORDS: List[str] = [
    # 控制流
    "if", "else", "for", "while", "do", "switch", "case", "break",
    "continue", "return", "goto", "default",
    # 数据类型
    "int", "float", "double", "char", "long", "short", "unsigned",
    "signed", "void", "struct", "union", "enum", "typedef",
    # 存储类
    "auto", "static", "extern", "register", "const", "volatile",
    # 预处理
    "#include", "#define", "#ifdef", "#ifndef", "#endif", "#pragma",
    # 标准库函数
    "printf", "scanf", "fprintf", "fscanf", "sprintf", "sscanf",
    "malloc", "calloc", "realloc", "free",
    "fopen", "fclose", "fread", "fwrite", "fgets", "fputs",
    "strlen", "strcpy", "strcat", "strcmp", "strncpy", "strncat",
    "memcpy", "memset", "memcmp",
    "exit", "abort", "atoi", "atof", "rand", "srand",
    # 概念词（中文）
    "指针", "数组", "函数", "递归", "作用域", "生命周期",
    "内存", "堆", "栈", "变量", "常量", "表达式", "运算符",
    "数据类型", "类型转换", "强制转换", "隐式转换",
    "分支", "循环", "条件", "判断", "嵌套",
    "结构体", "共用体", "枚举", "位运算",
    "文件", "输入", "输出", "格式化",
    "字符串", "字符数组", "二维数组",
    "形参", "实参", "返回值", "函数声明", "函数定义",
    "预处理", "宏定义", "头文件",
    "编译", "链接", "调试", "断点",
    "算法", "流程图", "伪代码", "复杂度",
    "自增", "自减", "赋值", "比较", "逻辑",
    "动态内存", "内存泄漏", "野指针", "空指针",
    "二级指针", "函数指针", "指针数组", "数组指针",
    "链表", "队列", "栈", "树", "排序", "查找",
]

# OCR 常见误识别纠错表（代码区专项）
OCR_CODE_FIXES: List[Tuple[str, str]] = [
    # printf 系列
    (r"\bprintf£\b",        "printf"),
    (r"\bprint£\b",         "printf"),
    (r"\bprintl\b",         "printf"),
    (r"\bprintf1\b",        "printf"),
    (r"\bprlntf\b",         "printf"),
    (r"\bprlnt£\b",         "printf"),
    (r"\bprint\s+£\s*\(",   "printf("),
    # scanf 系列
    (r"\bsconaf\b",         "scanf"),
    (r"\bsocanf\b",         "scanf"),
    (r"\bsccanf\b",         "scanf"),
    (r"\bscanl\b",          "scanf"),
    # include
    (r"\binciude\b",        "include"),
    (r"\bincIude\b",        "include"),
    (r"\bInciude\b",        "include"),
    # main
    (r"\bmaín\b",           "main"),
    (r"\bma1n\b",           "main"),
    (r"\bmaln\b",           "main"),
    # void
    (r"\bvold\b",           "void"),
    (r"\bvóid\b",           "void"),
    # return
    (r"\bretum\b",          "return"),
    (r"\breturn0\b",        "return 0"),
    # 头文件
    (r"\bstdio\.h\b",       "stdio.h"),
    (r"\bstdioh\b",         "stdio.h"),
    (r"\bstdlib\.h\b",      "stdlib.h"),
    (r"\bstring\.h\b",      "string.h"),
    (r"\bmath\.h\b",        "math.h"),
    # 其他
    (r"\bNULL\b",           "NULL"),
    (r"\bnu1l\b",           "NULL"),
    (r"\bnuIl\b",           "NULL"),
    (r"\bEOF\b",            "EOF"),
    (r"\.\.\.\.",           "..."),


    # 格式符 OCR 错误（字符串内 $ → %，负向后视避免双重替换）
    (r'%\$([dscflx])', r'%\1'),  # %$d → %d（OCR 在 % 后多加了 $）
    (r'(?<!%)\$d', '%d'),
    (r'(?<!%)\$s', '%s'),
    (r'(?<!%)\$f', '%f'),
    (r'(?<!%)\$c', '%c'),
    (r'(?<!%)\$lf', '%lf'),
    (r'(?<!%)\$ld', '%ld'),
    # 格式符前缀 t 误识别
    (r'\btd\b', '%d'),
    (r'\bta\b', '%d'),
    (r'\btlf\b', '%lf'),
    (r'\btf\b', '%f'),
    (r'\btc\b', '%c'),
    (r'\bts\b', '%s'),
    (r'#td', '%d'),
    (r'#ta', '%d'),
    # 操作符中 $ 误识别为 %
    (r'(\w)\$(\d)',  r'\1%\2'),
    # 字符串开头 * 误识别为 "
    # printf£ / printé（含后跟 (* 的变体）
    (r'printf£\(\*',   'printf("'),
    (r'printé\(\*',    'printf("'),
    (r'print£\(\*',    'printf("'),
    (r'printf£',        'printf'),
    (r'print£',         'printf'),
    (r'printé',         'printf'),
    # 字符串开头 * 或 ` 误识别为 "（放在 printé 规则之后）
    (r'printf\(\*',  'printf("'),
    (r'scanf\(\*',   'scanf("'),
    (r'printf\(\`',  'printf("'),
    (r'scanf\(\`',   'scanf("'),
    # 注释符 OCR 错误：7* / 7% → /*（不用分组避免 re.sub 无限循环）
    (r'\b7\*', '/*'),
    (r'\b7%', '/*'),
    # } else 误识别
    (r'^felse\s*if',   '} else if'),
    (r'^felse\b',      '} else {'),
    # print f( → printf(
    (r'\bprint\s+f\(',  'printf('),
    # 典型残留错误片段
    (r'0dd:%d,Even:sdvn', 'Odd:%d,Even:%d\\n'),
    (r'if\(表达式\)语句1执行流程:', 'if(表达式)语句1\\n执行流程:'),
    (r'if\(表达式\)语句1执行流程', 'if(表达式)语句1\\n执行流程'),
    (r'Enter n;', 'Enter n:'),
    (r'scanf\("1f£"', 'scanf("%lf"'),
    (r'count_even\+\+i', 'count_even++;'),
    (r'i<=ni\s*i\+\+', 'i<=n; i++'),
    (r'\} else \{\}', '} else {'),
    (r'\by=0;\s*/\s*HIE\s*x<0\s*\*/', 'y=0; /* x<0 */'),
    (r'\bys4ex/3;', 'y=4*x/3;'),
    (r'\byfa\s*%s\s*0<x<15', 'y=4*x/3 0<x<15'),
    (r'^上$', ''),
    (r'\b语句\s*mn\b', '语句 n'),
    (r'\b语句\s*n它\b', '语句 n。它'),
    (r'/\*\s*统计奇数的个数\s*/', '/* 统计奇数的个数 */'),
    (r'/\*\s*统计偶数的个数\s*\*/', '/* 统计偶数的个数 */'),
    (r'@\s*number\s*除以\s*2\s*的余数', '若 number 除以 2 的余数'),
    (r'G\s*number\s*除以\s*2\s*的余数', '若 number 除以 2 的余数'),
    # 进一步修复残留代码碎片
    (r'Odd:%d,Even:%d\n', r'Odd:%d,Even:%d\\n'),
    (r'Enter x;', 'Enter x:'),
    (r'A\*\s*输入提示\s*\*/', '/* 输入提示 */'),
    (r'输入 double 型数据用8%1f \*/', '/* 输入 double 型数据用 %lf */'),
    (r'\} else if\(x<=15\)\]', '} else if(x<=15) {'),
    (r'\bys4ex/3;', 'y=4*x/3;'),
    (r'count \+\+;', 'count++;'),
    (r'count \+\+\nif\(n!=0\)\{', 'count++;\n}\nif(n!=0){'),
    # ch04 循环结构代码块内修复
    (r'Scanf\("%1f', 'scanf("%lf'),
    (r'\bScanf\(', 'scanf('),
    (r'A\*\s*循环初始化\s*\*/', '/* 循环初始化 */'),
    (r'Je\s+i\s+RB\s+HAR\s*\*/', '/* i 记录循环次数 */'),
    (r'flag\*1\.0enominator', 'flag*1.0/denominator'),
    (r'pi=pi\+itemi', 'pi=pi+item;'),
    (r'%.4£', '%.4f'),
    (r'%.2£', '%.2f'),
    (r'%.1£', '%.1f'),
    # 通用：A* ... */ → /* ... */  (OCR 把 /* 识别成 A*)
    (r'A\*\s*([^*]{1,60}?)\s*\*/', r'/* \1 */'),
    (r'A\*\s*([^*]{1,60}?)\s*#/', r'/* \1 */'),
    # Genominator → denominator（代码块内）
    (r'\bGenominator\b', 'denominator'),
    # Je i RB HAR → i 记录循环次数
    (r'Je\s+i\s+RB\s+HAR\s*\*/', '/* i 记录循环次数 */'),
    (r'Je\s+i\s+RB\s+HAR', 'i 记录循环次数'),
    # 7+ ... */ → /* ... */  (OCR 把 /* 识别成 7+)
    (r'7\+\s*([^*]{1,80}?)\s*\*/', r'/* \1 */'),
    (r'7\+\s*([^*]{1,80}?)\s*\* \*/', r'/* \1 */'),
    # 7 BIN ... */ → /* ... */
    (r'7\s+BIN\s*:?([^*]{0,80}?)\s*\*/', r'/* \1 */'),
    # 循环初始化整行修复（A* 规则处理后的残留）
    (r'/\*\s*循环初始化\s*\*/i=1;.*', '/* 循环初始化 */\ni=1; /* i 记录循环次数 */'),
]

# 普通文本 OCR 纠错表（中文专项，非代码区）
OCR_TEXT_FIXES: List[Tuple[str, str]] = [
    # if 关键字误识别
    ("iL ",        "if "),
    (" iL(",       " if("),
    ("iL(",        "if("),
    ("it-else",    "if-else"),
    ("it else",    "if-else"),
    ("else-i",     "else-if"),
    (" 让语句",     " if 语句"),
    ("让语句",      "if 语句"),
    ("壮语句",      "if 语句"),
    ("证语句",      "if 语句"),
    (" 计语句",     " if 语句"),
    ("计语句",      "if 语句"),
    ("计语名",      "if 语句"),
    ("语名",        "语句"),
    ("话语句",      "if 语句"),
    ("if语名",      "if 语句"),
    (" else-计",    " else-if"),
    ("else-计",     "else-if"),
    (" else-认",    " else-if"),
    ("else-认",     "else-if"),
    (" 话套",        " 嵌套"),
    ("话套",         "嵌套"),
    # 中文 OCR 错字
    ("逮辑",        "逻辑"),
    ("逻揖",        "逻辑"),
    ("遥辑",        "逻辑"),
    ("远辑",        "逻辑"),
    ("被狂数",      "被猜数"),
    ("被狂",        "被猜"),
    ("被猛数",      "被猜数"),
    ("指钎",        "指针"),
    ("指釬",        "指针"),
    ("数纽",        "数组"),
    ("淡量",        "变量"),
    ("猪数",        "猜数"),
    ("篤数",        "猜数"),
    # 常见误识别
    ("^A if-",      "一个 if-"),
    ("^CS 采用",    "C 语言采用"),
    ("fl if-else",  "用 if-else"),
    ("语句 ni",      "语句 n"),
    ("else-iff",     "else-if"),
    ("switeh",       "switch"),
    ("非负整数 上",   "非负整数 n"),
    ("语句 n它",      "语句 n。它"),
    ("语句 mn",       "语句 n"),
    ("else-if语句else-if语句", "else-if语句"),
    ("读人",         "读入"),
    ("和否则",       "否则"),
    (" 这语句",      " 嵌套语句"),
    ("名和省略 else 的if 语句", "句和省略 else 的if 语句"),
    ("if(表达式)语句1执行流程:", "if(表达式)语句1\n执行流程:"),
    ("if(表达式)语句1执行流程",  "if(表达式)语句1\n执行流程"),
    # printf£ 各种变体（含空格）
    ("printf£",     "printf"),
    ("printé",      "printf"),
    ("print£",      "printf"),
    ("print f(",    "printf("),
    ("print  f(",   "printf("),
    ("scanf£",      "scanf"),
    ("print £(",    "printf("),
    ("print £ (",   "printf("),
    # 代码碎片在普通文本中的兜底修复
    ("ys4ex/3;",     "y=4*x/3;"),
    ("Enter x;",     "Enter x:"),
    ("count ++;",    "count++;"),
    ("if(score<60) {\ncount ++\nif(n!=0){", "if(score<60) {\ncount++;\n}\nif(n!=0){"),
    # 教材正文常见 OCR 文本修复
    ("getehar",      "getchar"),
    ("putehar",      "putchar"),
    ("US AA",        "注意"),
    ("Ail putchar",  "和 putchar"),
    ("BE ch",        "若 ch"),
    ("allb",         "a||b"),
    ("ALN",          "||"),
    ("Il (",         "|| ("),
    ("(ch>=\"a')&&(ch<=\"2\")", "(ch>='a')&&(ch<='z')"),
    ("Enter 8 characters;", "Enter 8 characters:"),
    ("Enter choice;", "Enter choice:"),
    ("提示输入mn 个数", "提示输入 n 个数"),
    ("提示输入mn个数", "提示输入 n 个数"),
    # 逻辑运算与练习区正文修复
    ("D BRIAR (ch==\"' Jil (ch=='\\n')", "(1) (ch==' ') || (ch=='\\n')"),
    ("Q BH RIAR (year %4==0 && year %100!=0)|| (year %400==0)", "(2) (year %4==0 && year %100!=0) || (year %400==0)"),
    ("小 将两个逻辑表达式连接起来", "|| 将两个逻辑表达式连接起来"),
    ("输出头年", "输出闰年"),
    ("判断闻年", "判断闰年"),
    ("阔年年份", "闰年年份"),
    ("【练习3-4】统计字符: 输入 1 TERR, An SEA, SIP REAR aE", "【练习3-4】统计字符: 输入 1 行字符,统计其中英文字母、空格或回车、数字字符和其他字符的个数。试编写相应程序。"),
    ("格或回车、数字字符和其他字符的个数。试编写相应程序。", ""),
    # ch04 循环结构 OCR 修复
    ("换名话说",       "换句话说"),
    ("格雷艾里公式",   "格雷戈里公式"),
    ("Scanf(\"%1f",  "scanf(\"%lf"),
    ("Scanf(",         "scanf("),
    ("print(\"",        "printf(\""),
    ("Genominator",    "denominator"),
    ("1.0enominator",  "1.0/denominator"),
    ("pi=pi+itemi",    "pi=pi+item;"),
    ("%.4£",           "%.4f"),
    ("%.2£",           "%.2f"),
    ("%.1£",           "%.1f"),
    ("%.0£",           "%.0f"),
    ("SEE - POR",       ""),
    # 括号类
    ("（ ",          "("),
    (" ）",          ")"),
]

# Post Normalize 规则表（集中配置）
PN_TEXT_STYLE_REGEX_RULES: List[Tuple[str, str]] = [
    (r"yfa\s+%s\s+0<x<15", "y=4*x/3  (0<x<15)"),
    (r"yfa\s*\S+\s*0<x<15", "y=4*x/3  (0<x<15)"),
    (r"(^|\s)A if-else", r"\1一个 if-else"),
    (r"(^|\s)CS 采用", r"\1C 语言采用"),
    (r"year 是头年", "year 是闰年"),
    (r"输入一个正整数\"\s*,?再输入\"\s*个字符", "输入一个正整数 n,再输入 n 个字符"),
    (r"输入一个正整数\"\s*,?再输入\"\s*个非负整数", "输入一个正整数 n,再输入 n 个非负整数"),
    (r"输入\"个字符时", "输入 n 个字符时"),
    (r"输入\s*个学生的成绩", "输入 n 个学生的成绩"),
    (r"提示输入mn\s*个数", "提示输入 n 个数"),
    # 第1章引言：OCR 将 if 识别为汉字
    (r"(?<![a-zA-Z0-9_])让(?!\s*我|\s*程序|\s*读者|\s*\w+\s*[，。；：])", "if"),
    (r"诺套", "嵌套"),
    (r"撕套", "嵌套"),
    (r"内谱", "内嵌"),
    (r"谍语句", "if 语句"),
    (r"诈语句", "if 语句"),
    (r"嵌套的谍", "嵌套的 if"),
    (r"嵌套的诈", "嵌套的 if"),
    (r"堪套", "嵌套"),
    (r"人C 语言", "C 语言"),
    (r"人 语言", "C 语言"),
    (r"(?m)^第工章引\s*$", "第 1 章 引言"),
    (r"(?m)^lg\s*$", ""),
]

PN_TEXT_STYLE_REPLACE_RULES: List[Tuple[str, str]] = [
    (")|| (", ") || ("),
    ("a&& b", "a&&b"),
    ("CSP 输入", "输入"),
    ("被舍奔了", "被舍弃了"),
    ("多辑运算对象", "逻辑运算对象"),
    ("热练的编程技能", "熟练的编程技能"),
    ("原樟输出", "原样输出"),
    ("\\m 是换行符", "\\n 是换行符"),
    ("换名话说", "换句话说"),
    ("格雷艾里公式", "格雷戈里公式"),
    ("格雷戈里公式求给定精度的 值", "格雷戈里公式求给定精度的 π 值"),
    ("popcom", "popcorn"),
    ("AE 5行显示菜单", "用下面 5 行显示菜单"),
    ("Odd: 3, Even; 1", "Odd: 3, Even: 1"),
    # 第1章引言残留
    ("HH;", ";"),
    ("isl;", "i=1;"),
    ("felse|", "} else {"),
    ("1elsel", "} else {"),
    ("Jelse|", "} else {"),
    ("le1sel", "} else {"),
    ("secanf(", "scanf("),
    ("faetorial(", "factorial("),
    ("Funetion", "Function"),
    ("Pseudoe Code", "Pseudocode"),
    ("Strueture", "Structure"),
    ("Portability", "Portability"),
    ("人C 语言", "C 语言"),
    ("人 语言", "C 语言"),
    ("##inelude", "#include"),
    ("##include", "#include"),
    ("引信人了", "引入了"),
    ("嵌套的计", "嵌套的 if"),
    ("嵌套的让", "嵌套的 if"),
    ("诺配对", "if 配对"),
    ("让书写", "if 书写"),
    ("让最好", "if 最好"),
    ("让数量", "if 数量"),
    ("让相匹", "if 相匹"),
    ("else 和放的", "else 和 if 的"),
    ("else 与放", "else 与 if"),
    ("else 与第二个放", "else 与第二个 if"),
    ("else 与第一个让", "else 与第一个 if"),
    ("else 和第一个半", "else 和第一个 if"),
    ("最靠近它的、没有与别的 else 匹配过的 计", "最靠近它的、没有与别的 else 匹配过的 if"),
    ("内和嵌的诈省略", "内嵌的 if 省略"),
    ("4 if-else 语句中的语句 2", "若 if-else 语句中的语句 2"),
    ("如果 if-else 语句的内蔡语句", "如果 if-else 语句的内嵌语句"),
    ("从内层到外层一一对应", "从内层到外层一一对应"),
    ("嵌套的 i-else", "嵌套的 if-else"),
    ("嵌套的谍语句", "嵌套的 if 语句"),
    ("嵌套的诈语句", "嵌套的 if 语句"),
]

PN_IO_REGEX_RULES: List[Tuple[str, str]] = [
    (r"^(Enter\s+[^:：]{1,50})[;；]\s*", r"\1: "),
    (r"^(Input\s+[^:：]{1,80})[;；]\s*", r"\1: "),
    (r"^(Type in an expression)[;；]\s*", r"\1: "),
]

PN_IO_REPLACE_RULES: List[Tuple[str, str]] = [
    ("[0] Exit", "[0] exit"),
]

PN_EXERCISE_REWRITE_PREFIX_RULES: List[Tuple[str, str]] = [
    (
        "【练习3-4】统计字符:",
        "【练习3-4】统计字符: 输入 1 行字符,统计其中英文字母、空格或回车、数字字符和其他字符的个数。试编写相应程序。",
    ),
    (
        "【练习3-1】例 3-4 Hf AEF",
        "【练习3-1】例 3-4 采用 else-if 语句实现三个分支,请验证三组测试用例是否正确,是否需要增加测试用例?若需要,请给出具体测试用例并运行程序。",
    ),
]

PN_EXERCISE_DROP_EXACT_RULES: List[str] = [
    "格或回车、数字字符和其他字符的个数。试编写相应程序。",
    "分支是否正确,已经设计了三组测试用例,请问还需要增加测试用例吗? 为什么?如果要",
    "增加,请给出具体的测试用例并运行程序。",
    "total/n); /* 分母不能为 0 */",
    "0.0); /* 当 n 为 0 时,平均分为 0 */",
    "count);",
    "/* 提示输入学生人数 n */",
    # 第1章严重损坏行
    "DSP ABH break 时,如果表达式的值与常量表达式 2 的值相等,不但执行语句段",
    "2,还执行其后的所有语句段,即执行语句段 2~语句段 n+1。",
    "CS EFI WE EI, ANE MR case ch>='0' \u0026\u0026 ch<='9'。",
    "lg",
    # 第4章噪声行
    "SEE - POR A IMA AY Ta, 55 2. 4 节例 2-8 相似,循环算式都是:",
    "A",
    "Scanf",
    " A IMA AY Ta, 55 2. 4 节例 2-8 相似,循环算式都是:",
    "的a\u00ab",
    "Tw 1 1 1",
    "a",
    "一=1-一+一-一+...",
    "A IMA AY Ta, 55 2. 4 节例 2-8 相似,循环算式都是:",
    "4 3°05 7",
]

# 全角→半角（使用 unicodedata 方式，避免手写映射出错）
def _fullwidth_to_halfwidth(text: str) -> str:
    result = []
    for ch in text:
        code = ord(ch)
        # 全角空格
        if code == 0x3000:
            result.append(' ')
        # 全角ASCII可见字符 (！ to ～)
        elif 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        else:
            result.append(ch)
    return ''.join(result)

# ─────────────────────────────────────────────
# 步骤 1：编码标准化
# ─────────────────────────────────────────────

def _step1_normalize_encoding(text: str) -> str:
    """统一全角→半角、引号、控制字符、换行符"""
    # 统一换行
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 删除控制字符（保留 \t \n）
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # 全角 → 半角
    text = _fullwidth_to_halfwidth(text)
    # 统一引号
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    # 统一破折号
    text = re.sub(r"[\u2012\u2013\u2014\u2015\ufe58]", "-", text)
    # 统一省略号
    text = re.sub(r"[\u2026\u22ef]{1,2}", "...", text)
    # 列表符号标准化：行首的 。© ◎ ○ 。 → ·
    text = re.sub(r"^[。©◎○●□▪▸]\s+", "· ", text, flags=re.MULTILINE)
    # 多个空格 → 单空格（不动换行）
    text = re.sub(r"[ \t]+", " ", text)
    return text


# ─────────────────────────────────────────────
# 步骤 2：页眉页脚识别与删除
# ─────────────────────────────────────────────

_HEADER_FOOTER_PATTERNS = [
    re.compile(r"^第\s*\d+\s*页\s*$"),
    re.compile(r"^Page\s*\d+\s*$", re.IGNORECASE),
    re.compile(r"^-\s*\d+\s*-$"),
    re.compile(r"^\d+\s*$"),                          # 纯页码
    re.compile(r"^[\s\-–—=*_·•◆▪]+$"),               # 纯分隔符
    re.compile(r"^\d+[。.\s]第\d+章"),                # 「046。第3章」格式页码
    re.compile(r"^\d+[。.]\s*(第\d+章|第[一二三四五六七八九十]+章)"),  # 数字。章节名
    re.compile(r"^第\d+章.{1,20}[。.]\s*\d+$"),       # 「第3章 分支结构。051」
    re.compile(r"^.{2,20}[。.]\s*\d{2,3}$"),          # 「章节名。页码」
    re.compile(r"^C语言.{0,15}(第\d+版|程序设计|教程)$"),
    re.compile(r"^(谭浩强|严蔚敏|苏小红).{0,20}$"),
]

def _step2_remove_header_footer(lines: List[str]) -> List[str]:
    """删除页眉页脚行"""
    # 规则1：正则直接命中
    def _is_hf_by_pattern(line: str) -> bool:
        s = line.strip()
        if not s:
            return False
        for pat in _HEADER_FOOTER_PATTERNS:
            if pat.match(s):
                return True
        return False

    # 规则2：统计高频短行（≤30字，出现≥3次）
    short_lines = [line.strip() for line in lines if 1 <= len(line.strip()) <= 30]
    freq = Counter(short_lines)
    repeated = {s for s, cnt in freq.items() if cnt >= 3}

    result = []
    for line in lines:
        s = line.strip()
        if _is_hf_by_pattern(s):
            continue
        if s in repeated and len(s) <= 30:
            continue
        result.append(line)
    return result


# ─────────────────────────────────────────────
# 步骤 3：目录页过滤
# ─────────────────────────────────────────────

_TOC_LINE_PAT = re.compile(
    r"([\u4e00-\u9fff\w]+.{2,40})[.\u2026]{3}\s*\d{1,4}$"
)
_TOC_SIMPLE_PAT = re.compile(r"\.{4}\s*\d{1,4}$")

def _is_toc_line(line: str) -> bool:
    s = line.strip()
    return bool(_TOC_LINE_PAT.search(s) or _TOC_SIMPLE_PAT.search(s))

def _step3_filter_toc(lines: List[str]) -> List[str]:
    """过滤目录页，但保留标题文字"""
    result: List[str] = []
    i = 0
    while i < len(lines):
        # 检测连续目录块（10行中≥6行是目录格式）
        window = lines[i: i + 10]
        toc_count = sum(1 for line in window if _is_toc_line(line))
        if toc_count >= 6:
            # 整块跳过，但提取标题文字
            while i < len(lines) and (_is_toc_line(lines[i]) or not lines[i].strip()):
                # 只保留标题部分（点号前）
                m = re.match(r"^([^.\u2026]{2,40})[.\u2026]{3}", lines[i].strip())
                if m:
                    title_text = m.group(1).strip()
                    if title_text:
                        result.append(title_text)
                i += 1
        else:
            result.append(lines[i])
            i += 1
    return result


# ─────────────────────────────────────────────
# 步骤 4：断行修复
# ─────────────────────────────────────────────

_CHAPTER_TITLE_PAT = re.compile(
    r"^(第[一二三四五六七八九十百\d]+[章节]|\d+\.\d|\d+\.\d+\.\d)"
)
_CODE_START_PAT = re.compile(
    r"^(#include|#define|int |void |char |float |double |long |struct |typedef |printf|scanf|return |}/|{$)",
    re.IGNORECASE,
)
_SENTENCE_END_CHARS = set("。.!?！？；;:\n")
_MERGE_FORBIDDEN_END = set("。.!?！？；;:，")

def _is_chinese_dominant(s: str) -> bool:
    chinese = sum(1 for c in s if "\u4e00" <= c <= "\u9fff")
    return chinese > len(s) * 0.3

def _step4_fix_line_breaks(lines: List[str]) -> List[str]:
    """修复 OCR 断行，智能合并连续行"""
    result: List[str] = []
    i = 0
    while i < len(lines):
        current = lines[i]
        cs = current.rstrip()

        if i + 1 >= len(lines):
            result.append(cs)
            i += 1
            continue

        nxt = lines[i + 1].strip()

        # 不合并：当前行为空
        if not cs.strip():
            result.append(cs)
            i += 1
            continue

        # 不合并：下一行为空
        if not nxt:
            result.append(cs)
            i += 1
            continue

        # 不合并：下一行是章节标题或代码块标记
        if _CHAPTER_TITLE_PAT.match(nxt) or _CODE_START_PAT.match(nxt):
            result.append(cs)
            i += 1
            continue

        # 不合并：下一行是代码块边界
        if nxt in (_CODE_BLOCK_START, _CODE_BLOCK_END):
            result.append(cs)
            i += 1
            continue

        # 不合并：当前行末尾是明确的句末/段末标点
        if cs and cs[-1] in _MERGE_FORBIDDEN_END:
            result.append(cs)
            i += 1
            continue

        # 不合并：当前行已经很长（>60字），避免无限拼接
        if len(cs.strip()) > 60:
            result.append(cs)
            i += 1
            continue

        # 不合并：下一行以【或数字+点开头（例题、编号行）
        if re.match(r"^(【|\d+[.、])", nxt):
            result.append(cs)
            i += 1
            continue

        # 合并：英文连字符断行
        if cs.endswith("-") and nxt and nxt[0].islower():
            lines[i + 1] = cs[:-1] + nxt
            i += 1
            continue

        # 合并：中文段落断行（末尾非标点，下一行非标题，且当前行较短 <30字）
        if _is_chinese_dominant(cs) and nxt and not nxt[0].isdigit():
            if cs[-1] not in _SENTENCE_END_CHARS and len(cs.strip()) < 30:
                lines[i + 1] = cs + nxt
                i += 1
                continue

        # 合并：英文行（末尾小写字母，下一行小写字母开头，且当前行较短）
        if cs and cs[-1].islower() and nxt and nxt[0].islower() and len(cs.strip()) < 40:
            lines[i + 1] = cs + " " + nxt
            i += 1
            continue

        result.append(cs)
        i += 1
    return result


# ─────────────────────────────────────────────
# 步骤 5：代码块识别与保护
# ─────────────────────────────────────────────

_CODE_BLOCK_START = "[CODE_BLOCK_START]"
_CODE_BLOCK_END = "[CODE_BLOCK_END]"

_CODE_INDICATOR_PAT = re.compile(
    r"(#include|#define|void |int main|printf\s*\(|scanf\s*\(|\{\s*$|^\s*\}|return\s+\w|malloc\s*\(|if\s*\(|else\s*\{|else\s*if|for\s*\(|while\s*\(|switch\s*\(|case\s+\w|break\s*;|continue\s*;|\+\+i\b)",
    re.IGNORECASE,
)

def _looks_like_code(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    # 缩进行
    if line.startswith(("    ", "\t")):
        return True
    # 含代码特征关键字
    if _CODE_INDICATOR_PAT.search(s):
        return True
    # 行末是 | 且行内有括号或等号（典型 OCR 代码行）
    if s.endswith("|") and re.search(r"[()=]", s):
        return True
    # lelse| / }else / lelse / felse
    if re.match(r"^(lelse|felse|\}else|\}\s*else)", s):
        return True
    # 含 OCR 注释符 7* 或 7% 的行（代码注释）
    if re.search(r"7[*%]", s):
        return True
    # 含典型 C 代码赋值/操作符组合
    if re.search(r"(\w+\s*[+\-]?=\s*\w|\w+\+\+|\w+--)", s) and ";" in s:
        return True
    # 含格式字符串 %d %s %f 等
    if re.search(r'"[^"]*%[dsfcxoluf][^"]*"', s):
        return True
    return False

def _step5_protect_code_blocks(lines: List[str]) -> List[str]:
    """识别并标记代码块，并向后吞并短代码尾巴"""
    result: List[str] = []
    i = 0
    while i < len(lines):
        if _looks_like_code(lines[i]):
            code_lines: List[str] = []
            # 收集连续代码行，允许中间有≤2行空行，但不跨越明确的非代码长段落
            consecutive_blank = 0
            while i < len(lines):
                line = lines[i]
                if _looks_like_code(line):
                    code_lines.append(line)
                    consecutive_blank = 0
                    i += 1
                elif not line.strip():
                    consecutive_blank += 1
                    if consecutive_blank <= 2:
                        code_lines.append(line)
                        i += 1
                    else:
                        break
                else:
                    # 非空非代码行：如果很短（<=5字）或像代码语法，继续收
                    s = line.strip()
                    if len(s) <= 5 or re.match(r'^[{}|;]', s):
                        code_lines.append(line)
                        i += 1
                    else:
                        break
            # 去掉尾部空行
            while code_lines and not code_lines[-1].strip():
                code_lines.pop()
            if len(code_lines) >= 2:
                result.append(_CODE_BLOCK_START)
                result.extend(code_lines)
                result.append(_CODE_BLOCK_END)
            else:
                result.extend(code_lines)
        else:
            result.append(lines[i])
            i += 1

    def _looks_like_code_tail(s: str) -> bool:
        t = s.strip()
        if not t:
            return False
        if _looks_like_code(t):
            return True
        if re.match(r'^(\}|\{|\}\s*else\b|else\b)', t):
            return True
        if re.match(r'^[A-Za-z_]\w*\s*\+\+\s*;?$', t):
            return True
        if re.match(r'^/\*.*\*/$', t):
            return True
        if re.search(r'[;{}()]', t) and re.search(r'[A-Za-z_]', t):
            return True
        return False

    # 第二遍：把代码块后紧跟的短代码尾巴吞并回代码块
    merged: List[str] = []
    i = 0
    while i < len(result):
        if result[i] != _CODE_BLOCK_START:
            merged.append(result[i])
            i += 1
            continue

        block: List[str] = [_CODE_BLOCK_START]
        i += 1
        while i < len(result) and result[i] != _CODE_BLOCK_END:
            block.append(result[i])
            i += 1

        if i < len(result) and result[i] == _CODE_BLOCK_END:
            i += 1  # 跳过原 END，稍后补回

        # 吞并后续尾巴行（最多 8 行）
        tail: List[str] = []
        blank_seen = 0
        look = i
        while look < len(result) and len(tail) < 8:
            s = result[look]
            st = s.strip()
            if st in (_CODE_BLOCK_START, _CODE_BLOCK_END):
                break
            if _CHAPTER_TITLE_PAT.match(st):
                break
            if not st:
                if tail and blank_seen == 0:
                    tail.append(s)
                    blank_seen = 1
                    look += 1
                    continue
                break
            if _looks_like_code_tail(s):
                tail.append(s)
                look += 1
                continue
            break

        # 去掉尾巴末尾空行
        while tail and not tail[-1].strip():
            tail.pop()

        block.extend(tail)
        block.append(_CODE_BLOCK_END)
        merged.extend(block)
        i = look

    # 第三遍：合并紧邻代码块（END 后直接 START）
    compact: List[str] = []
    j = 0
    while j < len(merged):
        if (
            j + 1 < len(merged)
            and merged[j] == _CODE_BLOCK_END
            and merged[j + 1] == _CODE_BLOCK_START
        ):
            j += 1  # 跳过当前 END，下一轮会继续处理 START 后内容
            continue
        compact.append(merged[j])
        j += 1

    # 第四遍：规范化标记，去掉嵌套 START/孤立 END
    normalized: List[str] = []
    in_block = False
    for line in compact:
        if line == _CODE_BLOCK_START:
            if in_block:
                continue
            in_block = True
            normalized.append(line)
            continue
        if line == _CODE_BLOCK_END:
            if not in_block:
                continue
            in_block = False
            normalized.append(line)
            continue
        normalized.append(line)

    # 若文件末尾仍在代码块中，补一个 END
    if in_block:
        normalized.append(_CODE_BLOCK_END)

    return normalized


# ─────────────────────────────────────────────
# 步骤 6：OCR 误识别纠错
# ─────────────────────────────────────────────


# 全文通用：中文注释修复正则（模块级，避免每行重新编译）
_COMMENT_FIX_PAT = re.compile(r"/([一-鿿][^/]{0,30})/")
def _step6_ocr_correction(lines: List[str]) -> List[str]:
    """对代码区做专项 OCR 纠错，普通文本做通用纠错"""
    # 全文通用：修复中文注释格式 /中文...数字/ → /* 中文 */

    result: List[str] = []
    in_code = False
    for line in lines:
        if line == _CODE_BLOCK_START:
            in_code = True
            result.append(line)
            continue
        if line == _CODE_BLOCK_END:
            in_code = False
            result.append(line)
            continue

        s = line

        # 极短 OCR 噪声行直接丢弃
        if s.strip() in {"上", "下", "中", "a", "t", "I", "l", "i", "x", "X", "A"}:
            result.append("")
            continue

        # 全文通用注释修复（不论是否在代码块内）
        s = _COMMENT_FIX_PAT.sub(lambda m: f"/* {m.group(1).strip()} */", s)

        # 全文通用：过滤严重乱码行
        # 特征：含大量连续大写字母/空格，且中文极少，疑似 OCR 乱码
        non_ascii_ratio = sum(1 for c in s if ord(c) > 127) / max(len(s), 1)
        upper_space_ratio = sum(1 for c in s if c.isupper() or c == ' ') / max(len(s), 1)
        is_garbled = (
            len(s.strip()) > 5
            and non_ascii_ratio < 0.1          # 几乎没有中文
            and upper_space_ratio > 0.5        # 大量大写+空格
            and not re.search(r'[a-z]{3,}', s)  # 没有连续小写（不是正常英文代码）
        )
        # 行以 《 开头（OCR 乱码残留）
        is_angle_garbled = s.strip().startswith('《')
        if is_garbled or is_angle_garbled:
            result.append('')
            continue

        if in_code or _looks_like_code(s):
            # 代码区：应用 OCR 纠错正则表
            for pattern, replacement in OCR_CODE_FIXES:
                s = re.sub(pattern, replacement, s)
            # 循环初始化行特殊修复（A* 规则处理后残留 Je i RB HAR */）
            s = re.sub(r'(/\*\s*循环初始化\s*\*/)i=1;.*', r'\1\ni=1; /* i 记录循环次数 */', s)
            # 残留 Je i RB HAR */ 直接清除
            s = re.sub(r'Je\s+i\s+RB\s+HAR\s*\*/', '', s).rstrip()
            # 数字/字母混淆：l→1（数字上下文）
            s = re.sub(r"(?<=[=\s\(])l(?=[0-9])", "1", s)
            s = re.sub(r"(?<=[0-9])l(?=[\s\)\+\-\*\/;,])", "1", s)
            # | 误识别为 { 或 }
            stripped = s.rstrip()
            if stripped.endswith("|"):
                s = stripped[:-1].rstrip() + " {"
            if re.match(r"^\s*[|l]\s*$", s):
                s = "}"
            # else| → else {
            s = re.sub(r"\belse\s*\|", "else {", s)
            # lelse → } else
            s = re.sub(r"^lelse\b", "} else", s.strip())
            # print £( → printf(  (含空格变体)
            s = re.sub(r"\bprint\s*[£$]\s*\(", "printf(", s)
            s = re.sub(r"\bprint\s+[£$]\s*\(", "printf(", s)
        else:
            # 普通文本：中文 OCR 错字纠错
            for old, new in OCR_TEXT_FIXES:
                s = s.replace(old, new)
            # 普通文本中出现的代码函数修复
            s = re.sub(r'printf[£$]', 'printf', s)
            s = re.sub(r'print[£$]', 'printf', s)
            s = re.sub(r'printl\b', 'printf', s)
            s = re.sub(r'printé', 'printf', s)
            # 普通文本中 A* ... */ → /* ... */（OCR把/*识别成A*）
            s = re.sub(r'A\*\s*([^*]{1,80}?)\s*\*/', r'/* \1 */', s)
            s = re.sub(r'A\*\s*([^*]{1,80}?)\s*#/', r'/* \1 */', s)
            # 普通文本中 7+ ... */ → /* ... */（OCR把/*识别成7+）
            s = re.sub(r'7\+\s*([^*]{1,80}?)\s*\*/', r'/* \1 */', s)
            s = re.sub(r'7\s+BIN\s*:?([^*]{0,80}?)\s*\*/', r'/* \1 */', s)
            # Genominator → denominator（普通文本中出现）
            s = s.replace('Genominator', 'denominator')
            # printf(* → printf("  或  scanf(* → scanf("
            s = re.sub(r'(printf|scanf)\(\*', r'\1("', s)
            s = re.sub(r'(printf|scanf)\(\`', r'\1("', s)
            # 普通文本中出现的格式符 OCR 修复（兜底）
            s = re.sub(r'(?<!%)\$lf', '%lf', s)
            s = re.sub(r'(?<!%)\$ld', '%ld', s)
            s = re.sub(r'(?<!%)\$d', '%d', s)
            s = re.sub(r'(?<!%)\$s', '%s', s)
            s = re.sub(r'(?<!%)\$f', '%f', s)
            s = re.sub(r'(?<!%)\$c', '%c', s)
            s = re.sub(r'\btd\b', '%d', s)
            s = re.sub(r'\bta\b', '%d', s)
            s = re.sub(r'\btlf\b', '%lf', s)
            s = re.sub(r'\btf\b', '%f', s)
            s = re.sub(r'\btc\b', '%c', s)
            s = re.sub(r'\bts\b', '%s', s)
            s = s.replace('#td', '#%d').replace('#ta', '#%d')
            s = s.replace('Enter n;', 'Enter n:')
            s = s.replace('A*当mn 为0时,平均分为 0 */', '/* 当 n 为 0 时,平均分为 0 */')
            s = s.replace('if(表达式)语句1执行流程:', 'if(表达式)语句1\n执行流程:')
            s = re.sub(r'(\w)\$(\d)', r'\1%\2', s)
            # 全角数字转半角（双保险）
            s = re.sub(r'[\uff10-\uff19]', lambda m: str(ord(m.group()) - 0xff10), s)
        result.append(s)
    return result


# ─────────────────────────────────────────────
# 步骤 7：章节结构识别
# ─────────────────────────────────────────────

@dataclass
class _SectionMark:
    level: int
    title: str
    line_idx: int

_TITLE_PATTERNS: List[Tuple[int, re.Pattern]] = [
    (1, re.compile(r"^第\s*[一二三四五六七八九十百\d]+\s*章\s*[\u4e00-\u9fff\w]{2,40}")),
    (2, re.compile(r"^第\s*[一二三四五六七八九十\d]+\s*节\s*[\u4e00-\u9fff\w]{2,30}")),
    (2, re.compile(r"^\d+\.\d+\s+[\u4e00-\u9fff\w]{2,30}")),
    (3, re.compile(r"^\d+\.\d+\.\d+\s+[\u4e00-\u9fff\w]{2,30}")),
    (2, re.compile(r"^【[\u4e00-\u9fff\w]{2,20}】")),
    (2, re.compile(r"^\[[\u4e00-\u9fff\w]{2,20}\]")),
]

def _detect_section_marks(lines: List[str]) -> List[_SectionMark]:
    marks: List[_SectionMark] = []
    for idx, line in enumerate(lines):
        s = line.strip()
        if not s or s in (_CODE_BLOCK_START, _CODE_BLOCK_END):
            continue
        for level, pat in _TITLE_PATTERNS:
            if pat.match(s):
                marks.append(_SectionMark(level=level, title=s[:60], line_idx=idx))
                break
    return marks


# ─────────────────────────────────────────────
# 步骤 8：噪声行过滤
# ─────────────────────────────────────────────

_NOISE_LINE_PATS = [
    re.compile(r"^[\s\-–—=*_·•◆▪■□▶→←↑↓]{2,}$"),
    re.compile(r"^图\s*\d+[-_—]\d+"),
    re.compile(r"^表\s*\d+[-_—]\d+"),
    re.compile(r"^Figure\s*\d+", re.IGNORECASE),
    re.compile(r"^Table\s*\d+", re.IGNORECASE),
    re.compile(r"^\(续\)$"),
    re.compile(r"^续表"),
    # 常见 OCR 噪声行
    re.compile(r"^\-\.\-\s*\|$"),
    re.compile(r"^\(a\)\s*中$"),
    re.compile(r"^上$"),
    re.compile(r"^ids\b", re.IGNORECASE),
    re.compile(r"^Ze\s+count", re.IGNORECASE),
    re.compile(r"^7\s+累加成绩"),
    # 图示区域常见乱码
    re.compile(r"^eax\s*>"),
    re.compile(r"^RRL\s*£$"),
    re.compile(r"^\*\s*表达式\d+\s*>"),
    re.compile(r"^真语句\d+.*\[ton\].*\[tan\]$"),
    re.compile(r"^运行结果\s*\d+Enter\s+x[:;]"),
]

def _step8_filter_noise_lines(lines: List[str]) -> List[str]:
    """过滤噪声行，压缩多余空行"""
    short_counter: Counter = Counter()
    for line in lines:
        s = line.strip()
        if 2 <= len(s) <= 15 and s not in (_CODE_BLOCK_START, _CODE_BLOCK_END):
            short_counter[s] += 1
    high_freq_noise = {s for s, cnt in short_counter.items() if cnt >= 4}

    result: List[str] = []
    blank_count = 0
    in_code = False

    for line in lines:
        s = line.strip()
        if s == _CODE_BLOCK_START:
            in_code = True
            blank_count = 0
            result.append(line)
            continue
        if s == _CODE_BLOCK_END:
            in_code = False
            result.append(line)
            continue
        if in_code:
            result.append(line)
            continue
        if not s:
            blank_count += 1
            if blank_count <= 1:
                result.append("")
            continue
        blank_count = 0
        if any(p.match(s) for p in _NOISE_LINE_PATS):
            continue
        if re.match(r"^\d{1,4}$", s):
            continue
        if s in high_freq_noise:
            continue
        result.append(line)
    return result


def _step9_repair_broken_snippets(lines: List[str]) -> List[str]:
    """修复高频 OCR 代码碎片（仅做保守修复）"""
    out: List[str] = []
    in_code = False
    prev_non_empty = ""

    for line in lines:
        s = line
        st = s.strip()

        if st == _CODE_BLOCK_START:
            in_code = True
            out.append(line)
            prev_non_empty = st
            continue
        if st == _CODE_BLOCK_END:
            in_code = False
            out.append(line)
            prev_non_empty = st
            continue

        if in_code:
            s = s.replace("ys4ex/3;", "y=4*x/3;")
            s = s.replace("Enter x;", "Enter x:")
            s = s.replace("Enter n;", "Enter n:")
            s = s.replace("count ++;", "count++;")
            s = s.replace("count ++", "count++")
            s = s.replace("scanf(\"1f£\"", "scanf(\"%lf\"")
            s = s.replace("if(op=='+) |", "if(op=='+') {")
            s = s.replace("} else if(op=='/) 1", "} else if(op=='/') {")
            s = s.replace("if(value2", "if(value2!=0)")
            s = s.replace("lelsel", "} else {")

            # 常见断裂：if(score<60){ count++; if(n!=0){ 之间缺一个 }
            if s.strip() == "if(n!=0){" and prev_non_empty == "count++;":
                out.append("}")

            if "输入 double 型数据用8%1f" in s:
                s = "/* 输入 double 型数据用 %lf */"
            if "A* 输入提示 */" in s:
                s = "/* 输入提示 */"

        # 全文：删除明显图示噪声残留
        if re.match(r"^真语句\d+.*\[ton\].*\[tan\]?$", st):
            continue

        out.append(s)
        if st:
            prev_non_empty = s.strip()

    return out


def _step9b_rebuild_known_examples(lines: List[str]) -> List[str]:
    """对已知高损坏示例做局部模板重建（例3-4、例3-5、字符输入输出示例）"""
    result = list(lines)

    def _find_code_block_after(anchor_idx: int, max_scan: int = 260) -> Tuple[int, int]:
        start = -1
        end = -1
        for j in range(anchor_idx, min(anchor_idx + max_scan, len(result))):
            if result[j].strip() == _CODE_BLOCK_START:
                start = j
                break
        if start == -1:
            return -1, -1
        for j in range(start + 1, min(start + max_scan, len(result))):
            if result[j].strip() == _CODE_BLOCK_END:
                end = j
                break
        return start, end

    # 例 3-5：四则运算表达式
    for i, line in enumerate(result):
        if "【例3-5】" not in line and "【例 3-5】" not in line:
            continue

        start, end = _find_code_block_after(i)
        if start == -1 or end <= start + 1:
            continue

        body = "\n".join(result[start + 1:end])
        if not any(tok in body for tok in ["lftc%1lf", "valuels", "lelsel", "|else if(op="]):
            continue

        rebuilt = [
            "printf(\"Type in an expression:\"); /* 提示输入一个表达式 */",
            "scanf(\"%lf%c%lf\", &value1, &op, &value2); /* 输入表达式 */",
            "if(op=='+') {",
            "    printf(\"=%.2f\\n\", value1+value2);",
            "} else if(op=='-') {",
            "    printf(\"=%.2f\\n\", value1-value2);",
            "} else if(op=='*') {",
            "    printf(\"=%.2f\\n\", value1*value2);",
            "} else if(op=='/') {",
            "    if(value2!=0) {",
            "        printf(\"=%.2f\\n\", value1/value2);",
            "    } else {",
            "        printf(\"Divisor can not be 0!\\n\");",
            "    }",
            "} else {",
            "    printf(\"Unknown operator!\\n\"); /* 运算符输入错误 */",
            "}",
        ]

        result = result[:start + 1] + rebuilt + result[end:]
        break

    # 例 3-3：统计学生成绩
    for i, line in enumerate(result):
        if "【例 3-3】" not in line and "【例3-3】" not in line:
            continue

        start, end = _find_code_block_after(i, max_scan=300)
        if start == -1 or end <= start + 1:
            continue

        body = "\n".join(result[start + 1:end])
        if not any(tok in body for tok in ["Enter score", "total/n", "Number of failures", "count =0"]):
            continue

        rebuilt = [
            "printf(\"Enter n:\");",
            "scanf(\"%d\", &n);",
            "total=0;",
            "count=0;",
            "for(i=1; i<=n; i++) {",
            "    printf(\"Enter score #%d:\", i); /* 提示输入成绩 */",
            "    scanf(\"%lf\", &score);",
            "    total=total+score;",
            "    if(score<60) {",
            "        count++;",
            "    }",
            "}",
            "if(n!=0) {",
            "    printf(\"Average=%.2f\\n\", total/n); /* 分母不能为 0 */",
            "} else {",
            "    printf(\"Average=%.2f\\n\", 0.0); /* 当 n 为 0 时,平均分为 0 */",
            "}",
            "printf(\"Number of failures=%d\\n\", count);",
        ]

        # 清理代码块后溢出的参数碎片
        # end 指向原 [CODE_BLOCK_END] 行，post_end 从 end+1 开始扫后续碎片
        post_end = end + 1
        drop_patterns = [
            re.compile(r"^total/n\);"),
            re.compile(r"^0\.0\);"),
            re.compile(r"^count\);"),
            re.compile(r"^/\*\s*提示输入学生人数"),
            re.compile(r"^\s*$"),
        ]
        while post_end < min(end + 40, len(result)):
            st = result[post_end].strip()
            if any(pat.match(st) for pat in drop_patterns):
                post_end += 1
            else:
                break

        result = result[:start + 1] + rebuilt + [_CODE_BLOCK_END] + result[post_end:]
        break

    # 例 3-9：简单计算器（switch 版本）
    for i, line in enumerate(result):
        if "【例 3-9】" not in line and "【例3-9】" not in line:
            continue

        start, end = _find_code_block_after(i, max_scan=300)
        if start == -1 or end <= start + 1:
            continue

        body = "\n".join(result[start + 1:end])
        if not any(tok in body for tok in ["case '+", "valuel", "kop", "Jelse|", "1elsel"]):
            continue

        rebuilt = [
            "printf(\"Type in an expression:\"); /* 提示输入一个表达式 */",
            "scanf(\"%d%c%d\", &value1, &op, &value2);",
            "switch(op) {",
            "    case '+': printf(\"=%d\\n\", value1+value2); break;",
            "    case '-': printf(\"=%d\\n\", value1-value2); break;",
            "    case '*': printf(\"=%d\\n\", value1*value2); break;",
            "    case '/':",
            "        if(value2!=0) {",
            "            printf(\"=%d\\n\", value1/value2);",
            "        } else {",
            "            printf(\"Divisor can not be 0!\\n\"); /* 对除数为 0 作特殊处理 */",
            "        }",
            "        break;",
            "    case '%':",
            "        if(value2!=0) {",
            "            printf(\"=%d\\n\", value1%value2);",
            "        } else {",
            "            printf(\"Divisor can not be 0!\\n\"); /* 对除数为 0 作特殊处理 */",
            "        }",
            "        break;",
            "    default: printf(\"Unknown operator\\n\"); break;",
            "}",
        ]

        result = result[:start + 1] + rebuilt + result[end:]
        break

    # 例 3-4：分段计算居民水费
    for i, line in enumerate(result):
        if "【例 3-4】" not in line and "【例3-4】" not in line:
            continue

        start, end = _find_code_block_after(i)
        if start == -1 or end <= start + 1:
            continue

        body = "\n".join(result[start + 1:end])
        if not any(tok in body for tok in ["ys4ex/3", "y=4*x/3", "Enter x", "2.5*x-10.5"]):
            continue

        rebuilt = [
            "printf(\"Enter x:\"); /* 输入提示 */",
            "scanf(\"%lf\", &x); /* 输入 double 型数据 */",
            "if(x<0) {",
            "    y=0;",
            "} else if(x<=15) {",
            "    y=4*x/3;",
            "} else {",
            "    y=2.5*x-10.5;",
            "}",
            "printf(\"f(%.2f)=%.2f\\n\", x, y);",
        ]

        result = result[:start + 1] + rebuilt + result[end:]
        break

    # 3.2.3 中字符输入输出示例
    for b in range(len(result)):
        if result[b].strip() != _CODE_BLOCK_START:
            continue
        e = -1
        for j in range(b + 1, min(b + 260, len(result))):
            if result[j].strip() == _CODE_BLOCK_END:
                e = j
                break
        if e == -1:
            continue

        body = "\n".join(result[b + 1:e])
        if not any(tok in body for tok in ["int first=1, k", "1elsel", "putehar", "Enter 8 characters"]):
            continue

        rebuilt = [
            "int first=1, k; /* first 的值表示将要处理的是否为输入的第 1 个字符 */",
            "printf(\"Enter 8 characters:\"); /* 输入提示 */",
            "for(k=1; k<=8; k++) {",
            "    ch=getchar(); /* 变量 ch 接收从键盘输入的一个字符 */",
            "    if(first==1) { /* 处理输入的第 1 个字符 */",
            "        putchar(ch);",
            "        first=0;",
            "    } else { /* 处理输入的第 2 个及以后的字符 */",
            "        putchar('-');",
            "        putchar(ch);",
            "    }",
            "}",
        ]

        result = result[:b + 1] + rebuilt + result[e:]
        break

    # 3.2.4 中判断英文字母示例（两段代码块）
    for i, line in enumerate(result):
        if "判断键盘输入的字符是否为英文字母" not in line:
            continue

        s1, e1 = _find_code_block_after(i, max_scan=180)
        if s1 == -1 or e1 <= s1 + 1:
            continue
        s2, e2 = _find_code_block_after(e1 + 1, max_scan=180)
        if s2 == -1 or e2 <= s2 + 1:
            continue

        body = "\n".join(result[s1 + 1:e2])
        if not any(tok in body for tok in ["It is a letter", "jelse|", "ch<='2'", ")1("]):
            continue

        rebuilt_1 = [
            "printf(\"Enter a character:\"); /* 输入提示 */",
            "ch=getchar(); /* 变量 ch 接收从键盘输入的一个字符 */",
            "if((ch>='a' && ch<='z') || (ch>='A' && ch<='Z')) {",
            "    printf(\"It is a letter.\\n\");",
            "} else {",
            "    printf(\"It is not a letter.\\n\");",
            "}",
        ]

        # 用一个完整代码块替换原来的两段碎块
        result = result[:s1 + 1] + rebuilt_1 + result[e2:]

        # 同步修复该示例后的典型运行结果错配
        io_start = e2
        io_end = min(e2 + 18, len(result))
        io_text = "\n".join(result[io_start:io_end])
        if "Enter a character" in io_text and "It is a letter." in io_text and "It is not a letter." in io_text:
            normalized_io = [
                "Enter a character: 9",
                "",
                "It is not a letter.",
                "",
                "Enter a character: A",
                "",
                "It is a letter.",
                "",
            ]
            # 仅覆盖示例输出片段，不动后续正文
            tail_idx = io_start
            max_scan = min(io_start + 30, len(result))
            while tail_idx < max_scan:
                line = result[tail_idx].strip()
                if line.startswith("逻辑表达式就是"):
                    break
                tail_idx += 1
            result = result[:io_start] + normalized_io + result[tail_idx:]

        break

    # 例 3-7：统计英文字母和数字字符
    for i, line in enumerate(result):
        if "【例3-7】" not in line and "【例 3-7】" not in line:
            continue

        start, end = _find_code_block_after(i, max_scan=260)
        if start == -1 or end <= start + 1:
            continue

        body = "\n".join(result[start + 1:end])
        if not any(tok in body for tok in ["digit =letter=other=0", "1elsel", "letter=%d, digit=%d"]):
            continue

        rebuilt = [
            "digit=letter=other=0; /* 置存放统计结果的 3 个变量的初值为零 */",
            "printf(\"Enter n:\");",
            "scanf(\"%d\", &n);",
            "getchar(); /* 读入并丢弃换行符 */",
            "printf(\"Enter %d characters:\", n);",
            "for(i=1; i<=n; i++) {",
            "    ch=getchar();",
            "    if((ch>='a' && ch<='z') || (ch>='A' && ch<='Z')) {",
            "        letter++;",
            "    } else if(ch>='0' && ch<='9') {",
            "        digit++;",
            "    } else {",
            "        other++;",
            "    }",
            "}",
            "printf(\"letter=%d, digit=%d, other=%d\\n\", letter, digit, other);",
        ]

        result = result[:start + 1] + rebuilt + result[end:]
        break

    # 例 3-8：自动售货机价格查询（跨两个代码块）
    for i, line in enumerate(result):
        if "【例3-8】" not in line and "【例 3-8】" not in line:
            continue

        s1, e1 = _find_code_block_after(i, max_scan=300)
        if s1 == -1 or e1 <= s1 + 1:
            continue
        s2, e2 = _find_code_block_after(e1 + 1, max_scan=300)
        if s2 == -1 or e2 <= s2 + 1:
            continue

        body = "\n".join(result[s1 + 1:e2])
        if not any(tok in body for tok in ["Select crisps", "switch( choice)", "price=%0.1f", "print f£"]):
            continue

        rebuilt = [
            "printf(\"[1] Select crisps\\n\");",
            "printf(\"[2] Select popcorn\\n\");",
            "printf(\"[3] Select chocolate\\n\");",
            "printf(\"[4] Select cola\\n\");",
            "printf(\"[0] exit\\n\");",
            "for(i=1; i<=5; i++) {",
            "    printf(\"Enter choice:\");",
            "    scanf(\"%d\", &choice);",
            "    if(choice==0) break;",
            "    switch(choice) {",
            "        case 1: price=3.0; break;",
            "        case 2: price=2.5; break;",
            "        case 3: price=4.0; break;",
            "        case 4: price=3.5; break;",
            "        default: price=0.0; break;",
            "    }",
            "    printf(\"price=%0.1f\\n\", price);",
            "}",
            "printf(\"Thanks\\n\");",
        ]

        result = result[:s1 + 1] + rebuilt + result[e2:]
        break

    # 统一修复“判断英文字母”示例后的运行结果错配
    for i in range(len(result) - 6):
        if result[i].strip() != "Enter a character: 9":
            continue
        # 第一组：9 应该不是字母
        if result[i + 2].strip() == "It is a letter.":
            result[i + 2] = "It is not a letter."

        # 第二组：将 ?_ 规范为 A，且应为字母
        for j in range(i + 3, min(i + 14, len(result) - 1)):
            if result[j].strip().startswith("Enter a character:"):
                result[j] = "Enter a character: A"
                if j + 2 < len(result) and result[j + 2].strip().startswith("It is"):
                    result[j + 2] = "It is a letter."
                break
        break

    return result


def _pn_normalize_text_line(s: str) -> str:
    """后规范层-文本风格：单行文本归一化（规则表驱动）"""
    out = s
    for pattern, repl in PN_TEXT_STYLE_REGEX_RULES:
        out = re.sub(pattern, repl, out)
    for old, new in PN_TEXT_STYLE_REPLACE_RULES:
        out = out.replace(old, new)
    return out


def _pn_normalize_example_io_line(s: str) -> str:
    """后规范层-示例I/O：统一提示符与菜单大小写（规则表驱动）"""
    out = s

    for pattern, repl in PN_IO_REGEX_RULES:
        out = re.sub(pattern, repl, out)
    for old, new in PN_IO_REPLACE_RULES:
        out = out.replace(old, new)

    return out


def _pn_rewrite_or_drop_line(s: str) -> Optional[str]:
    """后规范层：题面统一与碎片删除（规则表驱动）"""
    st = s.strip()

    for prefix, replacement in PN_EXERCISE_REWRITE_PREFIX_RULES:
        if st.startswith(prefix):
            return replacement

    if st in PN_EXERCISE_DROP_EXACT_RULES:
        return None

    return s


def _pn_dedupe_non_code(lines: List[str]) -> List[str]:
    """后规范层：仅在非代码区去重相邻重复行"""
    out: List[str] = []
    in_code = False
    for s in lines:
        st = s.strip()
        if st == _CODE_BLOCK_START:
            in_code = True
        elif st == _CODE_BLOCK_END:
            in_code = False

        if (not in_code) and out and st and out[-1].strip() == st:
            continue
        out.append(s)
    return out


def _pn_apply_text_style_pipeline(lines: List[str]) -> List[str]:
    """后规范子管道：文本风格规范"""
    normalized: List[str] = []
    for raw in lines:
        s = _pn_normalize_text_line(raw)
        s2 = _pn_rewrite_or_drop_line(s)
        if s2 is None:
            continue
        normalized.append(s2)

    normalized = _pn_dedupe_non_code(normalized)
    return normalized


def _pn_apply_example_io_pipeline(lines: List[str]) -> List[str]:
    """后规范子管道：示例输入输出规范"""
    return [_pn_normalize_example_io_line(line) for line in lines]


def _pn_fix_example37_brace(lines: List[str]) -> List[str]:
    """后规范层：例3-7代码块偶发缺失右花括号兜底"""
    fixed: List[str] = []
    in_code = False
    for line in lines:
        st = line.strip()
        if st == _CODE_BLOCK_START:
            in_code = True
        elif st == _CODE_BLOCK_END:
            in_code = False

        if in_code and "printf(\"letter=%d, digit=%d, other=%d\\n\"" in line:
            prev_non_empty = ""
            for k in range(len(fixed) - 1, -1, -1):
                if fixed[k].strip():
                    prev_non_empty = fixed[k].strip()
                    break
            if prev_non_empty != "}":
                fixed.append("}")

        fixed.append(line)
    return fixed


def _post_normalize_lines(lines: List[str]) -> List[str]:
    """独立后规范层：固定顺序执行文本风格与示例I/O规范"""
    normalized = _pn_apply_text_style_pipeline(lines)
    normalized = _pn_apply_example_io_pipeline(normalized)
    normalized = _pn_fix_example37_brace(normalized)
    return normalized


# ─────────────────────────────────────────────
# 步骤 9：段落重组
# ─────────────────────────────────────────────

def _step9_rebuild_segments(
    lines: List[str],
    section_marks: List[_SectionMark],
) -> List[Segment]:
    """按章节标题切分，重组为 Segment 列表"""
    if not section_marks:
        text = "\n".join(lines).strip()
        return [Segment(
            section_id="S01", title="全文", text=text,
            char_count=len(text), has_code=_CODE_BLOCK_START in text,
        )]

    segments: List[Segment] = []
    ch_counter = 0
    first_mark_idx = section_marks[0].line_idx
    if first_mark_idx > 0:
        pre_text = "\n".join(lines[:first_mark_idx]).strip()
        if pre_text:
            segments.append(Segment(
                section_id="S00", title="前言", text=pre_text,
                char_count=len(pre_text), has_code=_CODE_BLOCK_START in pre_text,
            ))

    for mi, mark in enumerate(section_marks):
        start_line = mark.line_idx
        end_line = section_marks[mi + 1].line_idx if mi + 1 < len(section_marks) else len(lines)
        seg_lines = lines[start_line + 1: end_line]
        text = "\n".join(seg_lines).strip()
        if mark.level == 1:
            ch_counter += 1
        section_id = f"CH{ch_counter:02d}" if mark.level == 1 else f"CH{ch_counter:02d}_{mi:02d}"
        if text and len(text) < 30 and segments:
            segments[-1].text += "\n" + mark.title + "\n" + text
            segments[-1].char_count = len(segments[-1].text)
            continue
        segments.append(Segment(
            section_id=section_id, title=mark.title, text=text,
            char_count=len(text), has_code=_CODE_BLOCK_START in text, level=mark.level,
        ))
    return segments


# ─────────────────────────────────────────────
# 步骤 10：关键词标注
# ─────────────────────────────────────────────

def _step10_annotate_keywords(segments: List[Segment]) -> List[Segment]:
    """为每个段落标注命中的 C 语言关键词"""
    for seg in segments:
        found: List[str] = []
        text_lower = seg.text.lower()
        for kw in C_KEYWORDS:
            if kw.lower() in text_lower:
                found.append(kw)
        seg.keywords = found[:30]  # 最多30个
    return segments


# ─────────────────────────────────────────────
# 公共入口
# ─────────────────────────────────────────────

def clean_pdf_text(raw_text: str) -> CleanResult:
    """
    主入口：对 PDF 提取的原始文字执行 10 步清洗
    返回 CleanResult（包含结构化 segments 和完整 clean_text）
    """
    raw_chars = len(raw_text)

    # Step 1
    text = _step1_normalize_encoding(raw_text)
    lines = text.split("\n")

    # Step 2
    lines = _step2_remove_header_footer(lines)

    # Step 3
    lines = _step3_filter_toc(lines)

    # Step 4
    lines = _step4_fix_line_breaks(lines)

    # Step 6 先执行：OCR 纠错（修复 print£、iL 等），再识别代码块
    lines = _step6_ocr_correction(lines)

    # Step 5：代码块识别（基于已纠错的文本，识别更准确）
    lines = _step5_protect_code_blocks(lines)

    # Step 6b：代码块识别后再跑一次 OCR 纠错（处理代码块内的残留）
    lines = _step6_ocr_correction(lines)

    # Step 6 已在上面执行，此处跳过（标记注释）
    # lines = _step6_ocr_correction(lines)

    # Step 7：先检测章节结构（在 step8 前，避免标题行被误删）
    section_marks = _detect_section_marks(lines)

    # Step 8
    lines = _step8_filter_noise_lines(lines)

    # Step 9：碎片修复（在降噪后进行，误伤更少）
    lines = _step9_repair_broken_snippets(lines)

    # Step 9b：已知高损坏示例的局部模板重建
    lines = _step9b_rebuild_known_examples(lines)

    # Post Normalize：统一后规范层（所有修复后统一收敛）
    lines = _post_normalize_lines(lines)

    # 重新检测（step8/9/post-normalize 可能移动行号，需重新扫描）
    section_marks = _detect_section_marks(lines)

    # Step 10
    segments = _step9_rebuild_segments(lines, section_marks)

    # Step 11
    segments = _step10_annotate_keywords(segments)

    clean_text = "\n".join(lines)
    chapters_detected = sum(1 for m in section_marks if m.level == 1)
    has_code = any(seg.has_code for seg in segments)

    return CleanResult(
        raw_chars=raw_chars,
        clean_chars=len(clean_text),
        chapters_detected=chapters_detected,
        has_code_blocks=has_code,
        segments=segments,
        clean_text=clean_text,
    )


def clean_text_to_str(raw_text: str) -> str:
    """快捷函数：只返回清洗后的纯文本（不需要结构化信息时使用）"""
    return clean_pdf_text(raw_text).clean_text
