# --- プレイヤー HTML (全スクロール・2番目表示維持・ジャンプ改善版) ---
    html_code = f"""
    <div id="app-wrapper">
        <div id="video-header">
            <video id="v" controls playsinline webkit-playsinline>
                <source src="data:video/mp4;base64,{video_base64}" type="video/mp4">
            </video>
            <div class="learning-controls">
                <button class="ctrl-btn" id="btn-prev">⏮</button>
                <button class="ctrl-btn" id="btn-repeat">🔁 <span id="r-status">OFF</span></button>
                <button class="ctrl-btn" id="btn-next">⏭</button>
            </div>
            <div class="jp-toggle-bar">
                <label><input type="checkbox" id="toggle-jp" checked> 日本語訳を表示</label>
            </div>
        </div>
        
        <div id="transcript-scroll-area">
            <div id="sl"></div>
            <div style="height: 600px;"></div> <!-- 下部余白：最後の文を2番目に置くために必要 -->
        </div>
    </div>

    <style>
        body, html {{ 
            margin: 0; padding: 0; height: 100vh; width: 100vw;
            overflow: hidden; font-family: sans-serif; background: #fff;
        }}
        #app-wrapper {{ display: flex; flex-direction: column; height: 100vh; width: 100vw; }}
        
        #video-header {{ flex-shrink: 0; background: #000; z-index: 1000; }}
        video {{ width: 100%; aspect-ratio: 16/9; display: block; }}
        
        .learning-controls {{ display: flex; gap: 2px; padding: 4px; background: #333; }}
        .ctrl-btn {{ flex: 1; padding: 15px; border: none; border-radius: 4px; background: #444; color: white; font-weight: bold; font-size: 1.2em; }}
        .ctrl-btn.active {{ background: #f44336; }}
        .jp-toggle-bar {{ padding: 6px 12px; font-size: 0.8em; color: #ccc; background: #222; border-bottom: 1px solid #444; }}

        #transcript-scroll-area {{
            flex-grow: 1;
            overflow-y: scroll;
            background: #fff;
            -webkit-overflow-scrolling: touch;
            padding: 0 !important;
            margin: 0 !important;
            scroll-behavior: smooth;
        }}

        .item {{ 
            padding: 12px 15px; 
            border-bottom: 1px solid #eee; 
            cursor: pointer;
            box-sizing: border-box;
            opacity: 0.3; /* 通常時は薄く */
            transition: opacity 0.3s, background 0.3s;
        }}
        
        /* 現在の文：くっきり＋黄色背景 */
        .item.active {{ 
            background: #fff9c4 !important; 
            border-left: 8px solid #2196f3; 
            opacity: 1;
        }}
        /* 前後の文：少し薄く見えるようにする */
        .item.near {{ 
            opacity: 0.8; 
        }}

        .en {{ font-weight: bold; font-size: 0.85em; line-height: 1.4; color: #000; }}
        .jp {{ font-size: 0.75em; color: #555; margin-top: 4px; }}
        .note {{ font-size: 0.7em; color: #d32f2f; margin-top: 3px; }}
        .hidden {{ display: none !important; }}

        @media (min-width: 600px) {{
            #app-wrapper {{ flex-direction: row; }}
            #video-header {{ width: 70%; height: 100vh; }}
            #transcript-scroll-area {{ width: 30%; height: 100vh; }}
        }}
    </style>

    <script>
        const data = {json.dumps(sub_data_js)};
        const v = document.getElementById('v');
        const sl = document.getElementById('sl');
        const ts = document.getElementById('transcript-scroll-area');
        let currentIdx = -1; 
        let isRepeat = false;

        // 全字幕を最初に一度だけ生成
        data.forEach((s, i) => {{
            const div = document.createElement('div');
            div.id = 's-'+i; 
            div.className = 'item';
            div.innerHTML = `<div class="en">${{s.text}}</div>
                             <div class="jp">${{s.translation}}</div>
                             ${{s.note ? `<div class="note">💡 ${{s.note}}</div>` : ''}}`;
            div.onclick = () => jumpTo(i);
            sl.appendChild(div);
        }});

        function updateDisplay(idx) {{
            const items = document.querySelectorAll('.item');
            items.forEach((item, i) => {{
                item.classList.remove('active', 'near');
                if (i === idx) {{
                    item.classList.add('active');
                }} else if (i === idx - 1 || i === idx + 1 || i === idx + 2) {{
                    item.classList.add('near');
                }}
            }});

            // 1つ前の文(idx-1)が一番上に来るようにスクロールさせる
            if (idx <= 0) {{
                ts.scrollTop = 0;
            }} else {{
                const prevEl = document.getElementById('s-'+(idx-1));
                if (prevEl) {{
                    ts.scrollTop = prevEl.offsetTop;
                }}
            }}
        }}

        function jumpTo(idx) {{
            if(idx < 0 || idx >= data.length) return;
            
            // リピートON時も即座にcurrentIdxを更新して新しい文でループさせる
            currentIdx = idx;
            v.currentTime = data[idx].start;
            v.play();
            updateDisplay(idx);
        }}

        document.getElementById('btn-prev').onclick = () => jumpTo(currentIdx - 1);
        document.getElementById('btn-next').onclick = () => jumpTo(currentIdx + 1);
        
        const rBtn = document.getElementById('btn-repeat');
        rBtn.onclick = () => {{
            isRepeat = !isRepeat;
            rBtn.classList.toggle('active', isRepeat);
            document.getElementById('r-status').innerText = isRepeat ? "ON" : "OFF";
        }};

        document.getElementById('toggle-jp').onchange = (e) => {{
            document.querySelectorAll('.jp').forEach(el => el.classList.toggle('hidden', !e.target.checked));
        }};

        v.addEventListener('timeupdate', () => {{
            const now = v.currentTime;

            // リピート処理（現在選択されているインデックスに基づいてループ）
            if (isRepeat && currentIdx !== -1) {{
                const s = data[currentIdx];
                if (now >= s.end - 0.05 || now < s.start - 0.1) {{
                    v.currentTime = s.start;
                    v.play();
                }}
                return;
            }}

            // 通常再生時の追従
            for (let i = 0; i < data.length; i++) {{
                if (now >= data[i].start && now < data[i].end) {{
                    if (currentIdx !== i) {{
                        currentIdx = i;
                        updateDisplay(i);
                    }}
                    break;
                }}
            }}
        }});
        
        // 初期状態の表示
        updateDisplay(0);
    </script>
    """
    st.components.v1.html(html_code, height=1200)