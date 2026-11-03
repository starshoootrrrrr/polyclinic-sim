import gspread
import pandas as pd
import streamlit as st

st.set_page_config(page_title="臨床実習 班決めシミュレーター", layout="wide")

st.title("🏥 臨床実習 班決めシミュレーター（ログイン＆削除機能付き）")

# --- スプレッドシート接続設定 ---
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/12WjfNuRxvx851A07wbDd8dZzq1BoJnP5jwgB0tJIe-U/edit?usp=drivesdk"


@st.cache_data(ttl=3)
def load_data():
    try:
        gc = gspread.public_authorize()
        sh = gc.open_by_url(SPREADSHEET_URL)
        worksheet = sh.get_worksheet(0)
        data = worksheet.get_all_records()
        return pd.DataFrame(data), worksheet
    except Exception as e:
        return pd.DataFrame(), None


df, worksheet = load_data()

# --- ログイン（ID認証）画面 ---
st.sidebar.header("🔐 ログイン / ID認証")
st.sidebar.caption("自分のIDを入力してログインしてください。")

input_id = st.sidebar.text_input(
    "あなたの匿名ID（パスワード）",
    type="password",
    help="ご自身で決めたIDを入力してください",
)
login_button = st.sidebar.button("ログイン / データの読み込み")

# セッション状態の管理
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = ""

if login_button:
    if not input_id:
        st.sidebar.error("IDを入力してください。")
    else:
        st.session_state.logged_in = True
        st.session_state.user_id = input_id
        st.sidebar.success(f"ID「{input_id}」でログインしました！")

# ログインしていない場合の案内
if not st.session_state.logged_in:
    st.warning(
        "👈 左側のサイドバーから**匿名ID（パスワード）**を入力してログインしてください。"
    )
    st.info(
        "※初めての方も、お好きなIDを入力してログインすると、そのIDで新規登録・保存が始まります。"
    )
else:
    current_user_id = st.session_state.user_id
    st.success(f"現在ログイン中のID: **{current_user_id}**")

    # 既にこのIDで登録されているデータを探す
    user_existing_data = None
    if not df.empty and "user_id" in df.columns:
        matched = df[df["user_id"].astype(str) == str(current_user_id)]
        if not matched.empty:
            user_existing_data = matched.iloc[0]

    # --- 希望入力・編集フォーム ---
    st.sidebar.markdown("---")
    st.sidebar.header("📥 希望の登録・変更")

    # 登録済みのデータがあれば初期値に反映
    def_gender = (
        user_existing_data["gender"]
        if user_existing_data is not None
        else "男子"
    )
    def_score = (
        int(user_existing_data["score"])
        if user_existing_data is not None
        else 500
    )
    def_group = (
        int(user_existing_data["group"])
        if user_existing_data is not None
        else 1
    )
    def_cap = (
        int(user_existing_data["capacity"])
        if user_existing_data is not None
        else 5
    )

    with st.sidebar.form("input_form"):
        gender = st.selectbox(
            "性別",
            ["男子", "女子"],
            index=0 if def_gender == "男子" else 1,
        )
        score = st.number_input(
            "テストの点数",
            min_value=0,
            max_value=1000,
            value=def_score,
            step=1,
        )
        group_choice = st.number_input(
            "希望する班番号 (1〜20)",
            min_value=1,
            max_value=20,
            value=def_group,
            step=1,
        )
        target_capacity = st.selectbox(
            "希望班の定員タイプ", [5, 6], index=0 if def_cap == 5 else 1
        )

        submitted = st.form_submit_button("この内容で保存・更新する")

    if submitted:
        if worksheet is not None:
            records = worksheet.get_all_records()
            existing_row = None
            for idx, r in enumerate(records, start=2):
                if str(r.get("user_id")) == str(current_user_id):
                    existing_row = idx
                    break

            new_row = [
                str(current_user_id),
                gender,
                int(score),
                int(group_choice),
                int(target_capacity),
            ]

            if existing_row:
                worksheet.update(f"A{existing_row}:E{existing_row}", [new_row])
                st.sidebar.success("データを更新しました！")
            else:
                worksheet.append_row(new_row)
                st.sidebar.success("新しい希望を登録しました！")

            st.cache_data.clear()
            st.rerun()
        else:
            st.sidebar.error("スプレッドシートへの接続に失敗しました。")

    # --- 登録データの削除機能 ---
    if user_existing_data is not None:
        st.sidebar.markdown("---")
        if st.sidebar.button(
            "❌ 登録データを完全に削除する", type="secondary"
        ):
            if worksheet is not None:
                records = worksheet.get_all_records()
                for idx, r in enumerate(records, start=2):
                    if str(r.get("user_id")) == str(current_user_id):
                        worksheet.delete_rows(idx)
                        break
                st.cache_data.clear()
                st.sidebar.success("登録データを削除しました。")
                st.rerun()

    # --- 全体の集計・判定表示 ---
    st.markdown("---")
    st.header("📊 全体の集計＆判定状況")

    if df.empty:
        st.info("まだデータが提出されていません。")
    else:
        results = []
        for g in range(1, 21):
            group_df = df[df["group"] == g]
            males = group_df[group_df["gender"] == "男子"].sort_values(
                by="score", ascending=False
            )
            females = group_df[group_df["gender"] == "女子"].sort_values(
                by="score", ascending=False
            )

            n_m = len(males)
            n_f = len(females)

            cap = (
                group_df["capacity"].iloc[0]
                if not group_df.empty
                else (5 if g <= 10 else 6)
            )

            status = "正常"
            passed_m = 0
            passed_f = 0

            if cap == 5:
                if n_m == 5 and n_f == 5:
                    status = "⚠️ 全員決め直し対象"
                else:
                    max_m = 3 if n_m > n_f else 2
                    max_f = 5 - max_m
                    passed_m = min(n_m, max_m)
                    passed_f = min(n_f, max_f)

                    if n_m > max_m or n_f > max_f:
                        status = "⚡ 点数選考発生中"
                    else:
                        status = "✅ 確定枠内"
            else:
                max_m = 3
                max_f = 3
                passed_m = min(n_m, max_m)
                passed_f = min(n_f, max_f)

                if n_m > max_m or n_f > max_f:
                    status = "⚡ 点数選考発生中"
                else:
                    status = "✅ 確定枠内"

            results.append(
                {
                    "班番号": f"{g}班",
                    "種別": f"{cap}人班",
                    "男子希望者数": n_m,
                    "女子希望者数": n_f,
                    "男子通過枠": f"{passed_m} 名",
                    "女子通過枠": f"{passed_f} 名",
                    "ステータス": status,
                }
            )

        res_df = pd.DataFrame(results)


        def highlight_status(val):
            if "⚠️" in str(val):
                return "background-color: #ffcccc; color: red; font-weight: bold;"
            elif "⚡" in str(val):
                return "background-color: #fff3cd; color: #856404;"
            elif "✅" in str(val):
                return "background-color: #d4edda; color: #155724;"
            return ""


        st.dataframe(
            res_df.style.map(highlight_status, subset=["ステータス"]),
            use_container_width=True,
        )

        # 自分の現在位置の確認
        st.markdown("---")
        st.subheader("🔍 あなたの登録状況と通過判定")
        if user_existing_data is not None:
            u_g = user_existing_data["group"]
            u_gender = user_existing_data["gender"]
            u_score = user_existing_data["score"]

            same_group_same_gender = df[
                (df["group"] == u_g) & (df["gender"] == u_gender)
            ].sort_values(by="score", ascending=False)
            rank = (
                list(same_group_same_gender["user_id"].astype(str)).index(
                    str(current_user_id)
                )
                + 1
            )

            st.info(
                f"現在の希望: **{u_g}班 ({u_gender})** ／ 入力点数: **{u_score}点**"
            )
            st.success(
                f"同性内の希望者 {len(same_group_same_gender)} 人中、あなたの順位は **{rank} 位** です！"
            )
        else:
            st.warning(
                "まだあなたの希望データが保存されていません。左のサイドバーから登録してください。"
            )
