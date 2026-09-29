"""Japanese curriculum text (学習指導要領: 中学 2021〜, 高校 2022〜) for the shared unit ids.

Grades follow where the topic is taught in Japan, which differs from Korea in places
(三平方の定理 is 中3, 一次不等式 and 循環小数 are 数学I, 剰余の定理 is 数学II).
"""

from __future__ import annotations

from studymate.solve.curriculum_types import UnitText

CHECK = "求めた答えをもとの式に代入して、成り立つか確かめる。"
# Answer conventions for choice problems (Korean 수능-style ① ~ ⑤).
CHOICE = "選択肢（①〜⑤）があるときは番号で答える（韓国の修能の短答式は0〜999の整数）。"

# Korean CSAT (수능) math units, placed where 学習指導要領 teaches them (数学Ⅰ・Ⅱ・Ⅲ・A・B・C).
CSAT_TEXT: dict[str, UnitText] = {
    "s1_exp_log": UnitText(
        grade="数学Ⅱ",
        name="指数と対数",
        examples="\\sqrt[3]{8} \\times 4^{\\frac{1}{2}}, \\log_2 12 - \\log_2 3, a^{\\frac{2}{3}} \\times a^{\\frac{1}{3}}, 常用対数 \\log_{10} 2 = 0.3010",
        concept="累乗根と指数の拡張: a>0 のとき a^m a^n = a^{m+n}, (a^m)^n = a^{mn}, a^{\\frac{m}{n}} = \\sqrt[n]{a^m}。"
        "対数の定義: a^x = M ⇔ x = \\log_a M (a>0, a≠1, M>0)。性質: \\log_a MN = \\log_a M + \\log_a N, "
        "\\log_a \\frac{M}{N} = \\log_a M - \\log_a N, \\log_a M^k = k\\log_a M, 底の変換 \\log_a b = \\frac{\\log_c b}{\\log_c a}。",
        method=(
            "累乗根は有理数の指数になおす（\\sqrt[3]{8} = 8^{\\frac{1}{3}}）",
            "底を素因数分解して同じ底にそろえる",
            "対数は性質で1つにまとめるか、底の変換公式で底をそろえる",
            "指数法則・対数の性質で計算する",
        ),
        notation="\\log_a M の a を底、M を真数という。常用対数は \\log_{10} と底を書き、数学Ⅲの自然対数は \\log x（底 e を省略）と書く。"
        + CHOICE,
        pitfalls="\\log_a(M+N) を \\log_a M + \\log_a N としてしまう、底の条件・真数条件を忘れる、負の数に有理数の指数を使う。",
        check="対数は指数になおして（a^{答え} = M）成り立つか、累乗根は累乗してもとの値にもどるか確かめる。",
    ),
    "s1_exp_log_function": UnitText(
        grade="数学Ⅱ",
        name="指数関数・対数関数",
        examples="2^{x+1} = 8, 4^x - 3 \\cdot 2^x - 4 = 0, \\log_2(x-1) < 3, y = 2^x のグラフの平行移動, 閉区間での最大値",
        concept="y = a^x と y = \\log_a x は互いに逆関数で、直線 y = x に関して対称。a>1 なら増加、0<a<1 なら減少。"
        "方程式は底をそろえて指数（真数）を比べ、不等式は底が1より小さいと不等号の向きが変わる。",
        method=(
            "対数があれば真数条件（真数 > 0）を先に求める",
            "底をそろえるか、a^x = t (t > 0) とおきかえる",
            "指数どうし（真数どうし）を比べて解く（0 < 底 < 1 なら不等号の向きを変える）",
            "真数条件・おきかえの条件との共通範囲を答えにする",
        ),
        notation="おきかえたら「a^x = t (t > 0)」と範囲も書く。" + CHOICE,
        pitfalls="真数条件を確かめずに不適な解を答えに入れる、底が1より小さいときに不等号の向きを変え忘れる、t > 0 を忘れる。",
        check="求めた解をもとの式に代入し、真数条件を満たすか確かめる。",
    ),
    "s1_trig_function": UnitText(
        grade="数学Ⅱ",
        name="三角関数",
        examples="\\sin\\frac{7}{6}\\pi, \\sin\\theta = \\frac{3}{5} (\\frac{\\pi}{2} < \\theta < \\pi) のとき \\cos\\theta, "
        "y = 2\\sin 3x の周期, 0 \\le x < 2\\pi で 2\\cos x - 1 = 0",
        concept="弧度法: 180° = π。動径上の点 (x, y), r = \\sqrt{x^2+y^2} について \\sin\\theta = \\frac{y}{r}, \\cos\\theta = \\frac{x}{r}, "
        "\\tan\\theta = \\frac{y}{x}。\\sin^2\\theta + \\cos^2\\theta = 1, \\tan\\theta = \\frac{\\sin\\theta}{\\cos\\theta}。"
        "y = a\\sin(bx + c) + d の周期は \\frac{2\\pi}{|b|}。",
        method=(
            "角を 2n\\pi \\pm \\theta, \\pi \\pm \\theta, \\frac{\\pi}{2} \\pm \\theta の形にして鋭角の三角関数で表す",
            "動径のある象限で符号を決める",
            "\\sin^2\\theta + \\cos^2\\theta = 1 などの相互関係で残りの値を求める",
            "方程式・不等式は単位円やグラフで、指定された範囲の解をすべて求める",
        ),
        notation="角は弧度法で \\frac{\\pi}{6} のように書く。" + CHOICE,
        pitfalls="象限による符号をまちがえる、周期を 2\\pi b としてしまう、範囲外の解を入れたり範囲内の解を落としたりする。",
        check="求めた値をもとの式に代入するか、単位円の図で符号と大きさを確かめる。",
    ),
    "s1_triangle_law": UnitText(
        grade="数学Ⅰ",
        name="正弦定理・余弦定理",
        examples="a = 3, b = 5, C = 60° のとき c, 外接円の半径 R, 三角形の面積 \\frac{1}{2}ab\\sin C",
        concept="正弦定理 \\frac{a}{\\sin A} = \\frac{b}{\\sin B} = \\frac{c}{\\sin C} = 2R。余弦定理 a^2 = b^2 + c^2 - 2bc\\cos A。"
        "面積 S = \\frac{1}{2}ab\\sin C。",
        method=(
            "与えられたもの（2辺とその間の角、3辺、2角と1辺、外接円）を整理する",
            "2辺と間の角・3辺なら余弦定理、角とその対辺の組があれば正弦定理を使う",
            "必要なら面積の公式を使う",
        ),
        notation="頂点 A, B, C の対辺の長さを a, b, c とする。" + CHOICE,
        pitfalls="正弦定理で 2R を忘れる、余弦定理で間の角でない角を使う、-2bc\\cos A の符号をまちがえる。",
        check="いちばん長い辺の対角がいちばん大きいか確かめ、別の定理でも計算してみる。",
    ),
    "s1_sequence": UnitText(
        grade="数学B",
        name="等差数列・等比数列",
        examples="等差数列で a_3 = 8, a_6 = 17 のとき a_{10}, 等比数列 a_2 = 6, a_5 = 48, 初項から第n項までの和 S_n",
        concept="等差数列 a_n = a + (n-1)d, S_n = \\frac{n\\{2a + (n-1)d\\}}{2}。等比数列 a_n = ar^{n-1}, "
        "S_n = \\frac{a(r^n - 1)}{r - 1} (r ≠ 1)。a_1 = S_1, a_n = S_n - S_{n-1} (n ≥ 2)。",
        method=(
            "初項と公差（公比）を a, d (a, r) とおく",
            "条件を a, d (a, r) の式で表す",
            "連立して a, d (a, r) を求める（公比の符号などは問題の条件で決める）",
            "一般項や和の公式に代入する",
        ),
        notation="数列は \\{a_n\\}、一般項は a_n、和は S_n と書く。" + CHOICE,
        pitfalls="第n項を a + nd としてしまう、公比の条件（正など）を無視する、S_n から a_n を求めるとき n = 1 を別に確かめない。",
        check="求めた初項と公差（公比）で、与えられた項をもう一度計算する。",
    ),
    "s1_sigma": UnitText(
        grade="数学B",
        name="数列の和（Σ）",
        examples="\\sum_{k=1}^{10}(2k+1), \\sum_{k=1}^{n} k^2, \\sum_{k=1}^{n}\\frac{1}{k(k+1)}",
        concept="Σの性質: 定数倍・和・差に分けられ、\\sum_{k=1}^{n} c = cn。\\sum k = \\frac{n(n+1)}{2}, "
        "\\sum k^2 = \\frac{n(n+1)(2n+1)}{6}, \\sum k^3 = \\left\\{\\frac{n(n+1)}{2}\\right\\}^2。分数の形は部分分数に分けて消去する。",
        method=(
            "Σの性質で項ごとに分ける",
            "公式に n を代入する",
            "分数の形は \\frac{1}{k(k+1)} = \\frac{1}{k} - \\frac{1}{k+1} と分けて前後の項を消す",
        ),
        notation="\\sum_{k=1}^{n} a_k のように最初と最後の番号を書く。" + CHOICE,
        pitfalls="\\sum a_k b_k を \\sum a_k \\times \\sum b_k としてしまう、\\sum c を c としてしまう、項数を数えまちがえる。",
        check="n に小さい数を入れて、直接たした値と比べる。",
    ),
    "s1_recursion_induction": UnitText(
        grade="数学B",
        name="漸化式と数学的帰納法",
        examples="a_1 = 2, a_{n+1} = a_n + 3 のとき a_{10}, a_{n+1} = 2a_n - 1, 数学的帰納法による証明",
        concept="初項と隣り合う項の関係式（漸化式）で数列が決まる。a_{n+1} - a_n = d なら等差、a_{n+1} = ra_n なら等比。"
        "数学的帰納法: [1] n = 1 で成り立つ、[2] n = k で成り立つと仮定すると n = k+1 でも成り立つ。",
        method=(
            "漸化式が等差・等比の形か確かめる",
            "そうでなければ n = 1, 2, 3, … と順に代入して必要な項まで求めるか、特性方程式で変形する",
            "証明は [1] と [2] の段階に分けて書く",
        ),
        notation="[1] n = 1 のとき、[2] n = k のとき成り立つと仮定すると … と書く。" + CHOICE,
        pitfalls="項の番号を1つずらして計算する、[2] で仮定を使わずに結論を書く。",
        check="求めた項を漸化式に代入して成り立つか確かめる。",
    ),
    "s2_limit_continuity": UnitText(
        grade="数学Ⅲ",
        name="関数の極限と連続性",
        examples="\\lim_{x\\to 2}\\frac{x^2-4}{x-2}, \\lim_{x\\to\\infty}\\frac{3x^2+1}{x^2-2x}, \\lim_{x\\to 1+0}f(x), "
        "\\lim_{x\\to 1}\\frac{x^2+ax+b}{x-1} = 3, x = a で連続になる条件",
        concept="\\frac{0}{0} の形は因数分解・有理化で約分し、\\frac{\\infty}{\\infty} の形は分母の最高次の項で割る。"
        "極限値が存在するには右側極限と左側極限が一致する。分母 → 0 で極限値が存在すれば分子 → 0。"
        "f(x) が x = a で連続 ⇔ \\lim_{x\\to a} f(x) = f(a)。",
        method=(
            "x = a を代入して形（\\frac{0}{0}, \\frac{\\infty}{\\infty}, \\infty - \\infty）を判断する",
            "形に合わせて因数分解・有理化・最高次の項で割る",
            "約分した式に代入して極限値を求める",
            "未定係数は「分母 → 0 なら分子 → 0」から式を立てる",
        ),
        notation="右側極限は \\lim_{x\\to a+0}、左側極限は \\lim_{x\\to a-0} と書く。" + CHOICE,
        pitfalls="約分する前に代入する、右側極限と左側極限を確かめない、連続の条件で f(a) を忘れる。",
        check="a にごく近い値を入れて、関数の値が極限値に近づくか確かめる。",
    ),
    "s2_derivative": UnitText(
        grade="数学Ⅱ",
        name="微分係数と導関数",
        examples="f(x) = x^3 - 2x^2 + 3x のとき f'(2), \\lim_{h\\to 0}\\frac{f(1+2h) - f(1)}{h}, (x^2+1)(x-3) の導関数, 平均変化率",
        concept="微分係数 f'(a) = \\lim_{h\\to 0}\\frac{f(a+h) - f(a)}{h}（接線の傾き）。(x^n)' = nx^{n-1}、"
        "定数倍・和・差の微分、積の微分 \\{f(x)g(x)\\}' = f'(x)g(x) + f(x)g'(x)。",
        method=(
            "極限の形は微分係数の定義に合うように変形する（\\frac{f(a+2h) - f(a)}{h} = 2 \\times \\frac{f(a+2h) - f(a)}{2h}）",
            "導関数 f'(x) を求める",
            "x = a を代入する",
        ),
        notation="導関数は f'(x), y', \\frac{dy}{dx} と書く。" + CHOICE,
        pitfalls="定義で分母と増分をそろえない、積の微分を f'(x)g'(x) としてしまう。",
        check="展開してから微分し直すか、近い2点の平均変化率と比べる。",
    ),
    "s2_derivative_use": UnitText(
        grade="数学Ⅱ",
        name="導関数の応用（接線・増減・極値・最大最小）",
        examples="曲線 y = x^3 - x 上の点 (1, 0) における接線, 3次関数 f(x) = x^3 - 3x + 2 の極大値, "
        "f(x) = x^3 + ax^2 + bx が x = -1 で極大、x = 3 で極小となる定数, 区間 0 \\le x \\le 3 での最大値, "
        "方程式 f(x) = k の実数解の個数",
        concept="点 (a, f(a)) における接線 y - f(a) = f'(a)(x - a)。f'(x) の符号で増減を調べ、+ から - に変わると極大、"
        "- から + に変わると極小。x = α で極値をとれば f'(α) = 0。区間での最大・最小は極値と端の値を比べる。"
        "実数解の個数は y = f(x) と y = k の共有点の個数。",
        method=(
            "f'(x) を求めて f'(x) = 0 となる x を求める",
            "極値をとる x = α, β が与えられたら f'(α) = f'(β) = 0 から定数を求める"
            "（3次関数なら f'(x) = 3(x - α)(x - β) と係数を比べると速い）",
            "増減表をかく",
            "接線は接点の x 座標から式を立て、最大・最小は極値と端の値を比べる",
            "グラフをかいて共有点の個数などを判断する",
        ),
        notation="増減表は x, f'(x), f(x) の行で作り、↗, ↘ で表す。" + CHOICE,
        pitfalls="f'(a) = 0 なら必ず極値だと思う（符号の変化を確かめる）、区間の端の値を比べない、接点と通る点を区別しない、"
        "定数を求めたあと f(α) に代入するとき (-1)^3, (-1)^2 の符号をまちがえる。",
        check="極値の前後で f'(x) の符号をもう一度確かめ、グラフの形と比べる。",
    ),
    "s2_integral": UnitText(
        grade="数学Ⅱ",
        name="不定積分と定積分",
        examples="\\int (3x^2 - 2x + 1)dx, \\int_0^2 (3x^2 - 2x + 1)dx, \\int_{-1}^{1}(x^3 + 3x^2)dx, \\frac{d}{dx}\\int_1^x (t^2 - 1)dt",
        concept="F'(x) = f(x) なら \\int f(x)dx = F(x) + C（C は積分定数）、\\int x^n dx = \\frac{1}{n+1}x^{n+1} + C。"
        "定積分 \\int_a^b f(x)dx = [F(x)]_a^b = F(b) - F(a)。\\frac{d}{dx}\\int_a^x f(t)dt = f(x)。",
        method=(
            "公式で各項の不定積分を求める",
            "[F(x)]_a^b に上端と下端を代入して F(b) - F(a) を計算する",
            "区間 [-a, a] では偶数次・奇数次の項に分けて簡単にする",
        ),
        notation="定積分は \\left[F(x)\\right]_a^b = F(b) - F(a) と書き、不定積分には積分定数 C をつける。"
        + CHOICE,
        pitfalls="積分定数 C を忘れる、F(a) - F(b) と逆にひく、\\int_a^x f(t)dt の微分で文字を取り違える。",
        check="求めた不定積分を微分して、被積分関数にもどるか確かめる。",
    ),
    "s2_integral_use": UnitText(
        grade="数学Ⅱ",
        name="定積分の応用（面積・速度と道のり）",
        examples="曲線 y = x^2 - 4x + 3 と x 軸で囲まれた部分の面積, 2曲線 y = x^2, y = 2x で囲まれた部分の面積, "
        "速度 v(t) = t^2 - 4t + 3 のとき t = 0 から t = 4 までに動いた道のり",
        concept="2曲線の間の面積 S = \\int_a^b |f(x) - g(x)|dx。数直線上を動く点: 位置の変化量 \\int_a^b v(t)dt、"
        "動いた道のり \\int_a^b |v(t)|dt（数学Ⅲ）。",
        method=(
            "共有点の x 座標を求めて積分区間を決める",
            "各区間でどちらのグラフが上か（符号）を決める",
            "（上 - 下）や |v(t)| を、符号が変わる点で区間を分けて積分する",
        ),
        notation="符号が変わる点で積分区間を分けて書く。" + CHOICE,
        pitfalls="符号が変わる区間を分けずに一度に積分する、位置の変化量と道のりを取り違える。",
        check="グラフをかいて、面積が正で大きさがだいたい合っているか確かめる。",
    ),
    "ps_counting": UnitText(
        grade="数学A",
        name="場合の数（順列・組合せ・重複組合せ）と二項定理",
        examples="{}_5\\mathrm{P}_2, 重複順列 3^4, 同じものを含む順列 \\frac{6!}{2!3!}, 円順列, 重複組合せ {}_3\\mathrm{H}_4, "
        "(x+2)^5 の展開式における x^3 の係数",
        concept="順列 {}_n\\mathrm{P}_r = \\frac{n!}{(n-r)!}、円順列 (n-1)!、重複順列 n^r、同じものを含む順列 \\frac{n!}{p!q!r!}、"
        "組合せ {}_n\\mathrm{C}_r = \\frac{n!}{r!(n-r)!}、重複組合せ {}_n\\mathrm{H}_r = {}_{n+r-1}\\mathrm{C}_r。"
        "二項定理（数学Ⅱ）の一般項 {}_n\\mathrm{C}_r a^{n-r}b^r。",
        method=(
            "順番を区別するか、重複を許すか、同じものがあるかを判断する",
            "条件があれば先に固定したりまとめたりして数え、「少なくとも」は余事象で数える",
            "公式で計算する",
            "二項定理は一般項の指数の条件から r を求めて係数を計算する",
        ),
        notation="{}_n\\mathrm{P}_r, {}_n\\mathrm{C}_r, {}_n\\mathrm{H}_r と書く。" + CHOICE,
        pitfalls="順列と組合せを取り違える、重複組合せで n と r を入れかえる、二項定理で定数の累乗を忘れる。",
        check="小さい場合を書き出して、公式の値と比べる。",
    ),
    "ps_probability": UnitText(
        grade="数学A",
        name="確率（加法定理・条件付き確率・反復試行）",
        examples="P(A) = \\frac{1}{3}, P(A \\cup B) = \\frac{1}{2} のとき P(A \\cap B), 条件付き確率 P_A(B), 独立な事象, "
        "さいころを4回投げて3の倍数の目がちょうど2回出る確率",
        concept="加法定理 P(A \\cup B) = P(A) + P(B) - P(A \\cap B)、余事象 P(\\overline{A}) = 1 - P(A)、"
        "条件付き確率 P_A(B) = \\frac{P(A \\cap B)}{P(A)}、乗法定理 P(A \\cap B) = P(A)P_A(B)、"
        "独立 ⇔ P(A \\cap B) = P(A)P(B)、反復試行 {}_n\\mathrm{C}_r p^r(1-p)^{n-r}。",
        method=(
            "事象を記号（A, B）で表す",
            "場合の数で数えるか、確率の公式で計算するかを決める",
            "「少なくとも」は余事象、「〜のとき〜である確率」は条件付き確率、くり返しは反復試行で式を立てる",
            "計算して既約分数で答える",
        ),
        notation="余事象は \\overline{A}、条件付き確率は P_A(B) と書く。" + CHOICE,
        pitfalls="排反と独立を取り違える、P_A(B) と P_B(A) を逆にする、反復試行で {}_n\\mathrm{C}_r を忘れる。",
        check="すべての場合の確率の和が1になるか、表やベン図で確かめる。",
    ),
    "ps_distribution": UnitText(
        grade="数学B",
        name="確率分布（二項分布・正規分布）",
        examples="確率変数 X が二項分布 B(20, \\frac{1}{4}) に従うとき V(4X+1), E(X) = 4, V(X) = 2 のとき E(X^2), "
        "正規分布 N(50, 4^2) で P(X \\ge 54), 正規分布表",
        concept="E(X) = \\sum x_i p_i, V(X) = E(X^2) - \\{E(X)\\}^2, \\sigma(X) = \\sqrt{V(X)}。E(aX+b) = aE(X) + b, V(aX+b) = a^2V(X)。"
        "二項分布 B(n, p): E(X) = np, V(X) = np(1-p)。正規分布 N(m, \\sigma^2) は Z = \\frac{X - m}{\\sigma} で標準化する。",
        method=(
            "確率分布（分布表、二項分布、正規分布）を確かめる",
            "平均・分散・標準偏差の公式を使う",
            "正規分布の確率は標準化して正規分布表の値をたしたりひいたりする",
        ),
        notation="二項分布 B(n, p)、正規分布 N(m, \\sigma^2) と書き、2つ目の値は分散である。" + CHOICE,
        pitfalls="V(aX+b) を aV(X) + b としてしまう、N(m, \\sigma^2) の \\sigma^2 を標準偏差と読む、標準化で分散で割ってしまう。",
        check="確率の和が1になるか、平均が分布の中心にあるか確かめる。",
    ),
    "ps_estimation": UnitText(
        grade="数学B",
        name="統計的な推測（標本平均・母平均の推定）",
        examples="母平均 m、母標準偏差 \\sigma の母集団から大きさ n の標本を取るときの標本平均 \\overline{X} の期待値と分散, "
        "信頼度95%の信頼区間",
        concept="E(\\overline{X}) = m, V(\\overline{X}) = \\frac{\\sigma^2}{n}, \\sigma(\\overline{X}) = \\frac{\\sigma}{\\sqrt{n}}。"
        "n が大きければ \\overline{X} は近似的に N(m, \\frac{\\sigma^2}{n}) に従う。信頼度95%の信頼区間 "
        "\\overline{X} - 1.96\\frac{\\sigma}{\\sqrt{n}} \\le m \\le \\overline{X} + 1.96\\frac{\\sigma}{\\sqrt{n}}（99%なら2.58）。",
        method=(
            "母平均、母標準偏差、標本の大きさを整理する",
            "標本平均の分布（平均・分散）を求める",
            "標準化して確率を求めるか、信頼区間の式に代入する",
        ),
        notation="標本平均は \\overline{X} と書く。" + CHOICE,
        pitfalls="\\sigma(\\overline{X}) を \\frac{\\sigma}{n} としてしまう、信頼区間の幅で2倍を忘れる。",
        check="標本の大きさが大きくなると信頼区間の幅が小さくなるか確かめる。",
    ),
    "calc_sequence_limit": UnitText(
        grade="数学Ⅲ",
        name="数列の極限と無限級数",
        examples="\\lim_{n\\to\\infty}\\frac{3n+1}{n}, \\lim_{n\\to\\infty}(\\sqrt{n^2+4n} - n), \\lim_{n\\to\\infty}\\frac{2^{n+1}+3^n}{3^{n+1}-2^n}, "
        "\\sum_{n=1}^{\\infty}\\left(\\frac{1}{3}\\right)^n",
        concept="\\frac{\\infty}{\\infty} の形は分母の最高次の項（いちばん大きい底の累乗）で割り、\\infty - \\infty の形は有理化する。"
        "\\{r^n\\} は -1 < r \\le 1 で収束。無限級数は部分和 S_n の極限で、無限等比級数 \\sum_{n=1}^{\\infty}ar^{n-1} = \\frac{a}{1-r} (|r| < 1)。",
        method=(
            "形（\\frac{\\infty}{\\infty}, \\infty - \\infty, 等比）を判断する",
            "最高次の項で割るか有理化して極限値を求める",
            "無限級数は部分和を求めて極限をとる（部分分数で消去）か、無限等比級数の公式を使う",
        ),
        notation="収束するときは極限値を、しないときは「発散する」と書く。" + CHOICE,
        pitfalls="無限等比級数で |r| < 1 を確かめない、初項をまちがえる、\\lim a_n = 0 なら級数が収束すると思う。",
        check="n に大きな数を入れて、極限値に近づくか確かめる。",
    ),
    "calc_transcendental": UnitText(
        grade="数学Ⅲ",
        name="指数・対数・三角関数の極限と導関数",
        examples="\\lim_{x\\to 0}\\frac{e^{2x}-1}{x}, \\lim_{x\\to 0}\\frac{\\log(1+3x)}{x}, \\lim_{x\\to 0}\\frac{\\sin 3x}{x}, "
        "(e^x\\sin x)', (\\log x)', 加法定理",
        concept="\\lim_{x\\to 0}(1+x)^{\\frac{1}{x}} = e, \\lim_{x\\to 0}\\frac{e^x - 1}{x} = 1, \\lim_{x\\to 0}\\frac{\\log(1+x)}{x} = 1, "
        "\\lim_{x\\to 0}\\frac{\\sin x}{x} = 1。(e^x)' = e^x, (a^x)' = a^x\\log a, (\\log x)' = \\frac{1}{x}, (\\sin x)' = \\cos x, "
        "(\\cos x)' = -\\sin x。",
        method=(
            "基本の極限の形になるように変形する（\\frac{\\sin 3x}{x} = 3 \\times \\frac{\\sin 3x}{3x}）",
            "微分の公式と積の微分法を使う",
            "必要な値を代入する",
        ),
        notation="自然対数は \\log x（底 e を省略）と書き、角は弧度法で計算する。" + CHOICE,
        pitfalls="\\lim\\frac{\\sin 3x}{x} を1としてしまう、(a^x)' で \\log a を忘れる、角を度で計算する。",
        check="小さい x を入れて極限値を見積もるか、導関数を積分してもとの関数にもどるか確かめる。",
    ),
    "calc_diff_methods": UnitText(
        grade="数学Ⅲ",
        name="いろいろな微分法",
        examples="商の微分 \\left(\\frac{x}{x^2+1}\\right)', 合成関数 (\\sin 2x)', 媒介変数 x = t^2, y = t^3 で \\frac{dy}{dx}, "
        "x^2 + y^2 = 4 で \\frac{dy}{dx}, 逆関数の微分, 第2次導関数",
        concept="商の微分 \\left(\\frac{f}{g}\\right)' = \\frac{f'g - fg'}{g^2}、合成関数 \\{f(g(x))\\}' = f'(g(x))g'(x)、"
        "媒介変数 \\frac{dy}{dx} = \\frac{dy/dt}{dx/dt}、陰関数は y を x の関数とみて両辺を x で微分、逆関数 \\frac{dx}{dy} = \\frac{1}{dy/dx}。",
        method=(
            "関数の形（商、合成、媒介変数、陰関数、逆関数）を見きわめる",
            "合う微分法を使う（合成関数は外側の微分 × 内側の微分）",
            "必要な点の値を代入する",
        ),
        notation="\\frac{dy}{dx}, f'(x)、第2次導関数 f''(x) と書く。" + CHOICE,
        pitfalls="合成関数で内側の微分を忘れる、逆関数の微分で点を取り違える、陰関数で y の項に \\frac{dy}{dx} をかけ忘れる。",
        check="できれば式を具体的に表してから微分し直して比べる。",
    ),
    "calc_derivative_use": UnitText(
        grade="数学Ⅲ",
        name="微分法の応用（接線・極値・変曲点・速度）",
        examples="曲線 y = xe^x 上の点における接線, f(x) = x\\log x の極小値, 変曲点, グラフの凹凸, 平面上を動く点の速度と加速度",
        concept="接線 y - f(a) = f'(a)(x - a)。f'(x) の符号で増減と極値、f''(x) の符号で凹凸（f'' > 0 で下に凸）を調べ、"
        "f''(x) の符号が変わる点が変曲点。平面運動: 速度 (\\frac{dx}{dt}, \\frac{dy}{dt})、速さ \\sqrt{(\\frac{dx}{dt})^2 + (\\frac{dy}{dt})^2}。",
        method=(
            "定義域を確かめ、f'(x), f''(x) を求める",
            "符号を調べて増減・凹凸の表をかく",
            "極値、変曲点、接線の方程式など聞かれている値を計算する",
        ),
        notation="「下に凸」「上に凸」という用語を使う。" + CHOICE,
        pitfalls="定義域（\\log x は x > 0）を確かめない、f''(a) = 0 なら必ず変曲点だと思う。",
        check="グラフの概形と増減・凹凸の表が合っているか確かめる。",
    ),
    "calc_integration": UnitText(
        grade="数学Ⅲ",
        name="いろいろな積分法（置換積分・部分積分）",
        examples="\\int_0^1 xe^x dx（部分積分）, \\int_0^1 2x(x^2+1)^3 dx（置換積分）, \\int_1^e \\log x\\,dx, \\int \\frac{f'(x)}{f(x)}dx",
        concept="置換積分 \\int f(g(x))g'(x)dx = \\int f(t)dt（t = g(x)、定積分なら積分区間も変える）。"
        "部分積分 \\int f(x)g'(x)dx = f(x)g(x) - \\int f'(x)g(x)dx。\\int \\frac{1}{x}dx = \\log|x| + C、\\int \\frac{f'(x)}{f(x)}dx = \\log|f(x)| + C。",
        method=(
            "内側の関数とその導関数があれば置換積分、多項式 × 指数・三角・対数関数の積なら部分積分を選ぶ",
            "部分積分は対数 > 多項式 > 三角 > 指数の順で微分する側を決める",
            "積分して区間を代入する",
        ),
        notation="置換は「x^2 + 1 = t とおくと 2x\\,dx = dt」と書く。" + CHOICE,
        pitfalls="置換したのに積分区間を変えない、部分積分の符号をまちがえる、\\int\\frac{1}{x}dx で絶対値を忘れる。",
        check="求めた不定積分を微分して、被積分関数にもどるか確かめる。",
    ),
    "calc_integral_use": UnitText(
        grade="数学Ⅲ",
        name="積分法の応用（区分求積法・面積・体積・曲線の長さ）",
        examples="\\lim_{n\\to\\infty}\\sum_{k=1}^{n}\\frac{1}{n}f\\left(\\frac{k}{n}\\right), 曲線 y = e^x と x 軸の間の面積, "
        "立体の体積 \\int_a^b S(x)dx, 曲線の長さ, 平面上を動く点の道のり",
        concept="\\lim_{n\\to\\infty}\\sum_{k=1}^{n}f\\left(\\frac{k}{n}\\right)\\frac{1}{n} = \\int_0^1 f(x)dx。面積 \\int_a^b |f(x) - g(x)|dx、"
        "体積 V = \\int_a^b S(x)dx、曲線の長さ \\int_a^b \\sqrt{1 + \\{f'(x)\\}^2}dx、道のり \\int_a^b \\sqrt{(\\frac{dx}{dt})^2 + (\\frac{dy}{dt})^2}dt。",
        method=(
            "求める量（面積、体積、長さ、道のり）に合う定積分の式を立てる",
            "積分区間を決める（区分求積法は \\frac{k}{n} を x、\\frac{1}{n} を dx にかえる）",
            "置換積分・部分積分で計算する",
        ),
        notation="区分求積法は \\lim\\sum の形を \\int の形に書きかえる。" + CHOICE,
        pitfalls="区分求積法で積分区間をまちがえる、断面積 S(x) を正しく立てない。",
        check="図をかいて、だいたいの大きさと比べる。",
    ),
    "geo_conic": UnitText(
        grade="数学C",
        name="2次曲線（放物線・楕円・双曲線）",
        examples="放物線 y^2 = 8x の焦点, 楕円 \\frac{x^2}{25} + \\frac{y^2}{9} = 1 の2つの焦点間の距離, "
        "双曲線 \\frac{x^2}{4} - \\frac{y^2}{5} = 1 の漸近線, 接線の方程式",
        concept="放物線 y^2 = 4px: 焦点 (p, 0)、準線 x = -p。楕円 \\frac{x^2}{a^2} + \\frac{y^2}{b^2} = 1 (a > b > 0): 焦点 (\\pm c, 0), "
        "c^2 = a^2 - b^2、焦点からの距離の和 2a。双曲線 \\frac{x^2}{a^2} - \\frac{y^2}{b^2} = 1: c^2 = a^2 + b^2、距離の差 2a、"
        "漸近線 y = \\pm\\frac{b}{a}x。",
        method=(
            "標準形になおして a, b, c（または p）を読む",
            "焦点、頂点、準線、漸近線を求める",
            "定義（距離の和・差、準線までの距離）や接線の公式で条件を式にする",
        ),
        notation="2次曲線は標準形で書く。" + CHOICE,
        pitfalls="楕円（c^2 = a^2 - b^2）と双曲線（c^2 = a^2 + b^2）の関係を取り違える、y^2 = 4px の 4p を p と読む。",
        check="求めた焦点と曲線上の1点で、定義（距離の和・差）が成り立つか確かめる。",
    ),
    "geo_vector": UnitText(
        grade="数学C",
        name="平面上のベクトル",
        examples="\\vec{a} = (2, 1), \\vec{b} = (1, -3) のとき \\vec{a} \\cdot \\vec{b}, |\\vec{a} + 2\\vec{b}|, 垂直条件, 内分点の位置ベクトル",
        concept="成分の計算と大きさ |\\vec{a}| = \\sqrt{a_1^2 + a_2^2}。内積 \\vec{a} \\cdot \\vec{b} = |\\vec{a}||\\vec{b}|\\cos\\theta = a_1b_1 + a_2b_2。"
        "垂直 ⇔ \\vec{a} \\cdot \\vec{b} = 0、平行 ⇔ \\vec{b} = k\\vec{a}。"
        "|m\\vec{a} + n\\vec{b}|^2 = m^2|\\vec{a}|^2 + 2mn\\,\\vec{a} \\cdot \\vec{b} + n^2|\\vec{b}|^2"
        "（例: |2\\vec{a} - \\vec{b}|^2 = 4|\\vec{a}|^2 - 4\\vec{a} \\cdot \\vec{b} + |\\vec{b}|^2）。",
        method=(
            "ベクトルを成分か、基準となる2つのベクトルで表す",
            "なす角が与えられたら、先に内積 \\vec{a} \\cdot \\vec{b} = |\\vec{a}||\\vec{b}|\\cos\\theta を計算しておく",
            "大きさは2乗して展開する（真ん中の項の係数 2mn を落とさない）",
            "垂直・平行・なす角の条件を内積の式にする",
        ),
        notation="ベクトルは \\vec{a} または \\overrightarrow{AB} と書く。" + CHOICE,
        pitfalls="|\\vec{a} + \\vec{b}| = |\\vec{a}| + |\\vec{b}| としてしまう、内積をベクトルだと思う、"
        "|m\\vec{a} + n\\vec{b}|^2 の展開で真ん中の項 2mn\\,\\vec{a} \\cdot \\vec{b} の 2 や m, n を落とす。",
        check="図で向きと大きさを確かめるか、成分で計算し直す。",
    ),
    "geo_space": UnitText(
        grade="数学C",
        name="空間図形と空間座標",
        examples="三垂線の定理, 正射影の面積 S\\cos\\theta, 2点 A(1, 2, 3), B(3, -1, 9) 間の距離, 内分点, 球面 (x-1)^2 + (y+2)^2 + z^2 = 9",
        concept="三垂線の定理（平面外の点から平面と平面上の直線に下ろした垂線の関係）。正射影: 長さ l\\cos\\theta、面積 S\\cos\\theta。"
        "2点間の距離 \\sqrt{(x_2-x_1)^2 + (y_2-y_1)^2 + (z_2-z_1)^2}、球面 (x-a)^2 + (y-b)^2 + (z-c)^2 = r^2。",
        method=(
            "垂線の足をとって直角三角形を見つける（三垂線の定理）",
            "必要なら座標を定めて距離・内分点の公式に代入する",
            "正射影は2平面のなす角 θ の \\cos\\theta をかける",
        ),
        notation="座標は (x, y, z) の順に書く。" + CHOICE,
        pitfalls="正射影で \\cos の代わりに \\sin をかける、2平面のなす角をまちがえる。",
        check="直角三角形で三平方の定理を使って長さを確かめ直す。",
    ),
}

GENERAL = UnitText(
    grade="共通",
    name="その他",
    examples="",
    concept="問題で与えられた条件と、求めるものを先に整理する。",
    method=("求めるものと与えられたものを整理する", "使える考え方や公式を思い出す", "1段階ずつ計算する"),
    check=CHECK,
)

TEXT: dict[str, UnitText] = {
    "m1_integer_rational": UnitText(
        grade="中1",
        name="正の数・負の数",
        examples="(-3)+(+5), (-2)×(-3)÷(+4), かっこと累乗がまざった計算",
        concept="加法の交換法則・結合法則。同符号の和は絶対値の和に共通の符号、異符号の和は絶対値の差に絶対値の大きい方の符号。"
        "乗法・除法は負の数が偶数個なら +、奇数個なら -。",
        method=(
            "累乗 → かっこの中 → 乗法・除法 → 加法・減法の順に計算する",
            "除法は逆数をかける乗法になおす",
            "先に符号を決めてから絶対値を計算する",
        ),
        notation="負の数はかっこでくくって書く（例: (-3)×(+2)）。",
        pitfalls="(-2)^2 と -2^2 を取り違える。",
        check="計算の順序を逆にたどって、もう一度計算してみる。",
    ),
    "m1_expression": UnitText(
        grade="中1",
        name="文字と式（一次式の計算）",
        examples="3(x-2)-2(x+1) を簡単にする, 式の値, 2x+3x",
        concept="同類項どうしだけをまとめられる。分配法則 a(b+c)=ab+ac。",
        method=(
            "かっこがあれば分配法則で先にはずす（かっこの前が - なら、中のすべての項の符号が変わる）",
            "同類項を集める",
            "係数どうしを計算して簡単にする",
        ),
        notation="かけ算の記号は省き、数を文字の前に書く（2×x → 2x、1×x → x）。",
        pitfalls="-(x-3) をはずすときに -3 の符号を変え忘れる。",
        check="文字にかんたんな数を入れて、もとの式と結果の式の値が同じか調べる。",
    ),
    "m1_linear_equation": UnitText(
        grade="中1",
        name="一次方程式",
        examples="2x-5=11, 3(x-1)=2x+4, \\frac{x}{2}+1=\\frac{x+3}{3}, 0.2x+0.5=1.1",
        concept="等式の性質: 両辺に同じ数をたしても、ひいても、かけても、（0でない数で）わっても等式は成り立つ。"
        "この性質を使って、項の符号を変えて反対の辺に移すことを移項という。",
        method=(
            "かっこがあれば分配法則ではずす",
            "係数が分数なら両辺に分母の最小公倍数を、小数なら10や100をかけて整数にする（分母をはらう）",
            "x の項を左辺に、数の項を右辺に移項する（符号を変えて一度に書く）",
            "両辺を整理して ax=b の形にする",
            "両辺を x の係数でわって解を求める",
        ),
        notation="移項は式を一度に書きかえる（2x-5=11 → 2x=11+5）。解は x=8 のように書く。"
        "「両辺に5をたす」過程を毎回別に書かない。",
        pitfalls="移項するときに符号を変え忘れる、分母をはらうときに全部の項にかけ忘れる。",
        check="x=解 をもとの方程式に代入して、左辺と右辺が等しいか確かめる。",
    ),
    "m1_proportion": UnitText(
        grade="中1",
        name="比例と反比例",
        examples="y は x に比例し、x=2 のとき y=6, y=\\frac{a}{x} のグラフ",
        concept="比例は y=ax (a≠0)、反比例は y=\\frac{a}{x} (a≠0)。与えられた x, y の値を代入して a を求める。",
        method=(
            "式の形を決める（y=ax または y=\\frac{a}{x}）",
            "与えられた x, y の値を代入して a を求める",
            "求めた式で、聞かれている値を計算する",
        ),
        check="求めた式に与えられた x, y の値をもう一度代入してみる。",
    ),
    "m2_rational_decimal": UnitText(
        grade="高1",
        name="実数（循環小数と分数）",
        examples="0.\\dot{3} を分数で表す, 循環小数の計算",
        concept="循環小数は分数で表せる。循環節の桁数だけ10の累乗をかけてひくと、くり返す部分が消える。",
        method=(
            "x=循環小数 とおく",
            "適当な10の累乗をかけた式をつくる",
            "2つの式をひいて x を分数で求め、約分する",
        ),
        check="求めた分数をわり算して、もとの循環小数になるか確かめる。",
    ),
    "m2_monomial_polynomial": UnitText(
        grade="中2",
        name="式の計算（単項式・多項式）",
        examples="a^3×a^4, (2x^2y)^3, (6x^2-4x)÷2x, 2(a+3b)-(a-b)",
        concept="指数法則: a^m×a^n=a^{m+n}, (a^m)^n=a^{mn}, (ab)^n=a^nb^n。多項式の加法・減法は同類項どうし。",
        method=("係数は係数どうし、文字は文字どうし計算する", "指数法則を使う", "同類項をまとめる"),
        notation="かけ算の記号を省き、文字はアルファベット順に書く。",
        pitfalls="(a^2)^3 を a^5 と指数をたしてしまう。",
        check="文字にかんたんな数を入れて値を比べる。",
    ),
    "m2_linear_inequality": UnitText(
        grade="高1",
        name="一次不等式",
        examples="3x-2<7, 2(x+1)\\ge x-3, 連立不等式",
        concept="不等式の性質: 両辺に同じ数をたしても、ひいても、正の数をかけても、わっても不等号の向きは変わらない。"
        "負の数をかけたり、わったりすると不等号の向きが変わる。",
        method=(
            "かっこ・分数・小数を整理する（一次方程式と同じやり方）",
            "x の項を左辺に、数の項を右辺に移項する",
            "ax>b の形に整理する",
            "両辺を x の係数でわる（負の数でわるときは不等号の向きを変える）",
        ),
        notation="解は x>3 のように書き、必要なら数直線に表す。",
        pitfalls="負の数でわるときに不等号の向きを変え忘れる。",
        check="境目の値と、解にふくまれる数を1つ入れて、不等式が成り立つか確かめる。",
    ),
    "m2_simultaneous": UnitText(
        grade="中2",
        name="連立方程式",
        examples="x+y=5, x-y=1 / 2x+3y=12, y=x+1",
        concept="2つの方程式を同時に満たす x, y を求める。1つの文字を消去する加減法と代入法がある。",
        method=(
            "係数をそろえやすければ加減法、一方の式が x= や y= の形なら代入法を選ぶ",
            "加減法: 一方の文字の係数の絶対値をそろえてから、2つの式をたすかひく",
            "残った一次方程式を解いて、一方の文字の値を求める",
            "求めた値を一方の式に代入して、もう一方の文字の値を求める",
        ),
        notation="それぞれの式に①、②と番号をつけ、「①+②」「①×2-②」のように書く。解は x=2, y=3 と書く。",
        pitfalls="2つの式をひくときに、すべての項の符号を変え忘れる。",
        check="求めた x, y を両方の式に代入して確かめる。",
    ),
    "m2_linear_function": UnitText(
        grade="中2",
        name="一次関数",
        examples="傾きが2で点(1, 3)を通る直線, 2点を通る一次関数, 切片",
        concept="一次関数 y=ax+b で a は傾き（x が1増えたときの y の増加量）、b は切片。"
        "変化の割合 = (y の増加量)/(x の増加量) = a。",
        method=(
            "求める式を y=ax+b とおく",
            "傾き a を求める（与えられているか、2点から計算する）",
            "通る点を代入して b を求める",
            "y=ax+b の形で答える",
        ),
        check="与えられた点を求めた式に代入してみる。",
    ),
    "m2_pythagoras": UnitText(
        grade="中3",
        name="三平方の定理",
        examples="直角三角形の斜辺を求める, 3, 4, x",
        concept="直角三角形で斜辺の長さを c、他の2辺を a, b とすると a^2+b^2=c^2。",
        method=(
            "斜辺（直角の向かいの辺）を見つける",
            "a^2+b^2=c^2 に代入する",
            "平方根を求める（長さは正の数）",
        ),
        check="3辺で a^2+b^2=c^2 が成り立つか計算してみる。",
    ),
    "m2_probability": UnitText(
        grade="中2",
        name="確率",
        examples="2つのさいころを投げて出た目の和が7になる確率, 硬貨を3枚投げる",
        concept="確率 = (その事柄が起こる場合の数)/(起こりうるすべての場合の数)。どの場合も同様に確からしいことが前提。",
        method=(
            "起こりうるすべての場合の数を求める",
            "その事柄が起こる場合をもれなく数える",
            "わって、約分した分数で答える",
        ),
        check="表や樹形図で場合をもう一度数えてみる。",
    ),
    "m3_square_root": UnitText(
        grade="中3",
        name="平方根",
        examples="\\sqrt{12}+\\sqrt{27}, \\frac{2}{\\sqrt{3}} の分母の有理化, \\sqrt{a^2}",
        concept="\\sqrt{a^2b}=a\\sqrt{b} (a>0)。分母に根号があるときは、分母と分子に同じ根号をかけて有理化する。",
        method=(
            "根号の中を素因数分解して、2乗の数を外に出す",
            "根号の中が同じものどうしを計算する",
            "分母を有理化する",
        ),
        notation="答えは根号の中をできるだけ小さい自然数にした形で書く。",
        pitfalls="\\sqrt{a}+\\sqrt{b}=\\sqrt{a+b} と計算してしまう。",
        check="2乗して、もとの値と同じになるか確かめる。",
    ),
    "m3_factorization": UnitText(
        grade="中3",
        name="式の展開と因数分解",
        examples="(x+3)(x-2) の展開, x^2-5x+6 の因数分解, x^2-9",
        concept="乗法公式: (a+b)^2=a^2+2ab+b^2, (a+b)(a-b)=a^2-b^2, (x+a)(x+b)=x^2+(a+b)x+ab。因数分解はその逆。",
        method=(
            "共通因数があれば先にくくり出す",
            "乗法公式の形（平方の形、和と差の積、x^2+(a+b)x+ab）を見つける",
            "かけて定数項、たして x の係数になる2つの数を見つける",
        ),
        check="因数分解した式を展開して、もとの式と同じになるか確かめる。",
    ),
    "m3_quadratic_equation": UnitText(
        grade="中3",
        name="二次方程式",
        examples="x^2-5x+6=0, 2x^2+3x-2=0, x^2-4x-1=0, (x-3)^2=5",
        concept="AB=0 ならば A=0 または B=0。因数分解できなければ平方の形にするか、解の公式 "
        "x=\\frac{-b\\pm\\sqrt{b^2-4ac}}{2a} を使う。",
        method=(
            "ax^2+bx+c=0 の形に整理する",
            "因数分解できれば因数分解して AB=0 を使う",
            "因数分解が難しければ解の公式を使う",
            "解を x=a, x=b（または x=a または x=b）と書く",
        ),
        notation="解が2つなら「x=2 または x=3」、重解は「x=3（重解）」と書く。",
        pitfalls="両辺を x でわって x=0 の解をなくしてしまう。",
        check="それぞれの解をもとの式に代入して0になるか確かめる。",
    ),
    "m3_quadratic_function": UnitText(
        grade="高1",
        name="二次関数",
        examples="y=2(x-1)^2+3 の頂点, y=x^2-4x+1 を平方完成する",
        concept="y=a(x-p)^2+q のグラフの頂点は (p, q)、軸は x=p。一般形は平方完成して標準形になおす。",
        method=("x^2 の係数でくくる", "平方完成する", "頂点と軸を読みとる"),
        check="標準形を展開して、もとの式と同じになるか確かめる。",
    ),
    "m3_trigonometry": UnitText(
        grade="高1",
        name="三角比",
        examples="sin 30°, 直角三角形で tan A",
        concept="直角三角形で sin A=(対辺)/(斜辺), cos A=(底辺)/(斜辺), tan A=(対辺)/(底辺)。",
        method=(
            "基準の角と、斜辺・対辺・底辺を決める",
            "定義どおりに比を書く",
            "30°, 45°, 60° は有名角の値を使う",
        ),
        check=CHECK,
    ),
    "h1_polynomial": UnitText(
        grade="高2",
        name="整式の割り算と剰余の定理",
        examples="(x^3+2x-1)÷(x-1) の余り, 恒等式の係数を決める",
        concept="剰余の定理: 整式 P(x) を x-a でわった余りは P(a)。恒等式はすべての x で成り立つので、係数比較法か数値代入法を使う。",
        method=("わる式が一次式なら剰余の定理で P(a) を計算する", "必要なら組立除法で商を求める"),
        check="(わる式)×(商)+(余り) を展開して、もとの式と比べる。",
    ),
    "h1_complex_quadratic": UnitText(
        grade="高2",
        name="複素数と二次方程式",
        examples="判別式で解を判別, 2つの解の和と積, x^2+2x+5=0 の虚数解",
        concept="判別式 D=b^2-4ac: D>0 異なる2つの実数解、D=0 重解、D<0 異なる2つの虚数解。"
        "解と係数の関係: \\alpha+\\beta=-\\frac{b}{a}, \\alpha\\beta=\\frac{c}{a}。",
        method=(
            "聞かれているのが解か、解の種類か、2つの解の和・積かを決める",
            "判別式か解と係数の関係を使う",
            "虚数解は i を使って表す (i^2=-1)",
        ),
        check=CHECK,
    ),
    "h1_inequality": UnitText(
        grade="高1",
        name="二次不等式・絶対値を含む不等式",
        examples="x^2-3x-4<0, |x-2|<3, 連立二次不等式",
        concept="二次不等式は、二次関数のグラフが x 軸より上か下かになる範囲で解く。|x-a|<b ⇔ -b<x-a<b。",
        method=(
            "対応する二次方程式の解を求める",
            "グラフ（下に凸・上に凸）を思い浮かべて範囲を決める",
            "絶対値は場合分けするか、定義を使って解く",
        ),
        check="範囲の中と外の数を1つずつ入れてみる。",
    ),
    "h1_counting": UnitText(
        grade="高1",
        name="場合の数（順列・組合せ）",
        examples="5人から2人を選んで1列に並べる, _5C_2",
        concept="順番を考えるなら順列 _nP_r、考えないなら組合せ _nC_r=\\frac{_nP_r}{r!}。",
        method=("順番を区別するかどうか判断する", "順列か組合せの式を立てる", "計算する"),
        check=CHECK,
    ),
    "h1_equation_of_figure": UnitText(
        grade="高2",
        name="図形と方程式",
        examples="2点間の距離, 直線の方程式, 円の方程式 (x-1)^2+(y+2)^2=9",
        concept="2点間の距離 \\sqrt{(x_2-x_1)^2+(y_2-y_1)^2}、円 (x-a)^2+(y-b)^2=r^2 の中心は (a, b)、半径は r。",
        method=("求める図形の式の形を決める", "与えられた条件を代入する", "標準形に整理する"),
        check=CHECK,
    ),
    **CSAT_TEXT,
}
