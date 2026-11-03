import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="臨床実習 班決めシミュレーター", layout="wide"
)

st.title("🏥 臨床実習 班決めリアルタイムシミュレーター")
st.caption(
    "※匿名で希望と点数を入力し、現在の確定状況や倍率を確認するためのシミュレーションツールです。"
)

# セッション状態の初期化（簡易データ保存用）
if "submissions" not in st.session_state:
    st.session_state.submissions = []

# サイドバー：データ入力フォーム
st.sidebar.header("📥 希望入力フォーム")
with st.sidebar.form("input_form", clear_on_submit=False):
    user_id = st.text_input(
        "匿名ID（パスワード）",
        help="自分の回答を変更・修正する際識別するために使います（例: 学籍番号末尾+好きな数字など）",
    )
    gender = st.selectbox("性別", ["男子", "女子"])
    score = st.number_input(
        "テストの点数",
        min_value=0,
        max_value=1000,
        value=500,
        step=1,
        help="同性内で順位判定に使用します",
    )
    group_choice = st.number_input(
        "希望する班番号 (1〜20)", min_value=1, max_value=20, value=1, step=1
    )
    target_capacity = st.selectbox(
        "希望班の定員タイプ",
        [5, 6],
        help="希望する班が5人班か6人班かを選択してください",
    )

    submitted = st.form_submit_button("希望を提出 / 更新")

if submitted:
    if not user_id:
        st.sidebar.error("匿名IDを入力してください。")
    else:
        # 既存IDの更新または新規追加
        existing_idx = next(
            (
                i
                for i, sub in enumerate(st.session_state.submissions)
                if sub["user_id"] == user_id
            ),
            None,
        )
        data = {
            "user_id": user_id,
            "gender": gender,
            "score": score,
            "group": group_choice,
            "capacity": target_capacity,
        }

        if existing_idx is not None:
            st.session_state.submissions[existing_idx] = data
            st.sidebar.success("登録データを更新しました！")
        else:
            st.session_state.submissions.append(data)
            st.sidebar.success("希望を提出しました！")

# データフレーム化
df = pd.DataFrame(st.session_state.submissions)

# 集計・判定メイン処理
st.header("📊 現在の集計＆判定状況")

if df.empty:
    st.info(
        "まだデータが提出されていません。左のフォームから希望を入力してください。"
    )
else:
    # 班ごとのループ処理
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

        # デフォルトの班定員設定（入力されたデータに基づく、なければ5人班想定）
        cap = (
            group_df["capacity"].iloc[0]
            if not group_df.empty
            else (5 if g <= 10 else 6)
        )

        status = "正常"
        passed_m = 0
        passed_f = 0

        # ルール判定
        if cap == 5:
            # 5人班ルール
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
            # 6人班ルール (3:3)
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
                "男子希望数": n_m,
                "女子希望数": n_f,
                "男子通過枠": f"{passed_m} 名",
                "女子通過枠": f"{passed_f} 名",
                "ステータス": status,
            }
        )

    res_df = pd.DataFrame(results)


    # 警告ハイライト処理
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

    st.markdown("---")
    st.subheader("🔍 自分の通過状況を確認する")
    check_id = st.text_input("登録した匿名IDを入力してください")

    if check_id:
        user_row = df[df["user_id"] == check_id]
        if user_row.empty:
            st.warning("該当するIDが見つかりません。")
        else:
            u_g = user_row["group"].values[0]
            u_gender = user_row["gender"].values[0]
            u_score = user_row["score"].values[0]

            same_group_same_gender = df[
                (df["group"] == u_g) & (df["gender"] == u_gender)
            ].sort_values(by="score", ascending=False)
            rank = (
                list(same_group_same_gender["user_id"]).index(check_id) + 1
            )

            st.write(
                f"**あなたの希望**: {u_g}班 ({u_gender}) / 入力点数: {u_score}点"
            )
            st.write(f"**同性内での順位**: {len(same_group_same_gender)}人中 **{rank}位**")
