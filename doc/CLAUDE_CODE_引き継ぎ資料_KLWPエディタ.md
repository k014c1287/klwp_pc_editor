# KLWP Desktop Editor — Claude Code 引き継ぎ資料

## 1. プロジェクト概要

**目的**: Android アプリ KLWP (Kustom Live Wallpaper Maker) のプリセット
ファイル (.klwp) を、Windows 上のスタンドアロンアプリで作成・編集し、
Android に転送して読み込ませる。

**現状**: Python + Tkinter + Pillow の責務分割済みパッケージ `klwp/`
として動作中。`klwp_editor.py` は起動と旧import互換だけを担う23行のファサード。
実プリセット `sizuka_home.klwp` を基準に確認中。2026-07-21に§7の優先タスクを完了し、2026-07-22にGlobal管理統合と要素ツリーのドラッグ並べ替えを追加。
「一部テキストの座標がずれている」問題は 2026-07-20 に修正済み
(原因はテキスト計測と描画の条件不一致。詳細は §5 末尾の修正メモ参照)

**動作要件**: Python 3.9+ / Pillow。exe 化は
`pyinstaller --onefile --windowed klwp_editor.py`。

**現行設計図**: クラス構成と主要処理のシーケンスは
`doc/KLWPエディタ_設計仕様.md` の Mermaid 図を参照すること。

**基準ファイル**: `sizuka_home.klwp`
(要素27個 / bitmaps 6枚 / fonts 4種 / 1080x2400 端末向け)。
回帰テストは常にこのファイルで行うこと。

**sample/ フォルダ**: `sizuka_home.klwp` に加え `genoblanc.klwp` (要素46個,
BitmapModule/KomponentModule含む) と `S041.klwp` (要素198個, Stack/Shape多用)
を配置。さらに公式KLWP 3.82 AOSP APK同梱プリセットからv1/v3/v4/v5を
無変更で追加した。出典とSHA-256は `sample/README.md` を参照すること。

### 2026-07-20 サンプル基準の描画改修

本資料の旧記述ではなく、3ファイルの `preset.json` と同梱portrait thumbnailを
正として描画系を改修した。現在は次に対応済み。

- BitmapModule（元画像の縦横比維持、`bitmap_width`、`bitmap_alpha`）
- プレビュー選択枠の8方向ハンドルによるShape自由リサイズ、Bitmap縦横比固定リサイズ。描画時の境界記録によりOverlap内の子要素も選択可能
- `internal_formulas` / `internal_globals` / `globals_list` のサンプル評価
- 背景画像の固定指定、BITMAP型Global紐付け、Kode数式による時間帯別切替の編集・プレビュー
- Overlapの全子要素wrap、StackのRIGHT/BOTTOMを含む整列
- Shape/Textおよび時計グループの回転、TRIANGLE
- `fx_shadow: OUTER`、`paint_stroke`、動的背景・色・幅・可視性
- preset_infoの縦横比自動採用、v10旧配置の互換補正
- GUIなしの `render_to_image()` と回帰・構造テスト（現在51テスト）
- Komponent倍率、線形／放射／Sweepグラデーション、主要blend mode
- ROTATE/SCALE/色フィルターとease、編集可能なKodeプレビュー値
- 全グローバル型・外部タップアクションの編集UI、adbワンクリック転送
- Switch専用管理画面を全型対応Global管理へ統合。ツールバーはルートGlobal、Komponent選択時の右ペインはローカルGlobalを別ボタンで編集
- 要素ツリーの種類・前面順表示、選択解除によるルート追加先への復帰、同一レイヤー内ドラッグ並べ替え

以降に残る「Bitmap/数式/影/回転が未実装」という記述は改修前の履歴であり、
上記が現行状態。未対応なのは主に公式Kode全関数、新Shader、Android固有の
実データ・アプリ一覧連携である。

---

## 2. .klwp ファイルフォーマット (リバースエンジニアリング結果)

実体は **ZIP アーカイブ**。構成:

```
preset.json      … デザイン本体 (すべての要素定義)
bitmaps/IMG<32桁hex> … 画像 (参照は kfile://org.kustom.provider/bitmaps/IMG<32桁hex>)
fonts/*.ttf      … 同梱フォント (参照は kfile://org.kustom.provider/fonts/名前.ttf)
komponents/      … (存在する場合) コンポーネント
preset_thumb_portrait.jpg / preset_thumb_landscape.jpg … サムネイル
```

画像IDは `IMG` にUUIDの32桁hexを続ける。旧エディタ版は誤って28桁へ
切り詰めていたため、読込時と保存時に `BitmapReferenceNormalizer` がZIP内の
画像名と `preset.json` 内の参照を同時に移行する。ZIPエントリーはKLWP実機の
生成形式に合わせ、UTF-8フラグとdata descriptorフラグ（`0x808`）を付与する。

### preset.json のトップ構造

```json
{
  "preset_info": {
    "width": 540, "height": 1200,   // ※信用してはならない (§3参照)
    "title": "...", "id": "uuid", "ts": <epoch ms>, "release": 381531008,
    "features": "LOCATION WEATHER ..." // 使用機能の列挙
  },
  "preset_root": {
    "internal_type": "RootLayerModule",
    "background_type": "IMAGE" | "SOLID",
    "background_bitmap": "kfile://...", "background_color": "#AARRGGBB",
    "internal_formulas": {"background_bitmap": "$if(..., gv(day), gv(night))$"},
    "internal_globals": {"background_bitmap": "day"},
    "globals_list": { <グローバル変数> },
    "viewgroup_items": [ <要素の配列> ]
  }
}
```

### 主な internal_type

| type | 説明 |
|---|---|
| RootLayerModule | ルート |
| OverlapLayerModule | 重ねレイヤー (子は同一領域に重なる) |
| StackLayerModule | 並べレイヤー (`config_stacking` で横/縦整列) |
| ShapeModule | 図形 (RECT/CIRCLE/OVAL/PATH) |
| TextModule | テキスト・数式 |
| FontIconModule | アイコン |
| ProgressModule | プログレス (リング/バー) |
| BitmapModule | 画像 (背景とは別に配置する画像要素、描画対応済み) |
| KomponentModule | コンポーネント (作者の署名付きサブレイヤー群。中身は通常のレイヤーと同じ viewgroup_items) |

(2026-07-20 追記) `genoblanc.klwp` に BitmapModule 3個・KomponentModule 2個
(アナログ時計コンポーネント) が実在することを確認。旧版の本表には
この2種が記載されていなかった。

### 重要キー早見表

**キー名の注意**: 以下は簡略表記。実ファイルの anchor/offset/padding 系は
すべて `position_` 接頭辞付き (`position_anchor`, `position_offset_x`,
`position_offset_y`, `position_padding_left/right/top/bottom`)。
`klwp/` の実装は正しくこの接頭辞を使用しているが、本資料の文中表記
(`anchor`, `offset_x` 等) と実キー名が異なる点に注意 (2026-07-20 確認)。

- 色: `paint_color` = `#AARRGGBB` (AA=不透明度)。`paint_style: "STROKE"` で枠線のみ、線幅は `paint_stroke` (旧実装で `paint_stroke_width` も見ること)
- 図形追加と右プロパティ欄では `ColorControl` により、色見本、OSカラーピッカー、不透明度0–100%、カラーコード直接入力を同期する
- 図形: `shape_width/height/corners`、`shape_type: "PATH"` のとき `shape_path` に SVG 風パス (M/L/H/V/A/C/Q/Z、座標は 0-100 グリッド)。`shape_rotate_mode` / `shape_rotate_offset` は描画対応済み
- エフェクト: `fx_mask: "BLURRED"` = すりガラス、`fx_mask: "CLIP_NEXT"` = 次の兄弟要素を切り抜くマスク、`fx_shadow: "OUTER"` = 外側グロー（いずれも近似描画対応）
- 画像塗り: `fx_gradient: "BITMAP"` + `fx_gradient_bitmap: "kfile://..."`
- テキスト: `text_expression` (数式 `$...$` 含む)、`text_size`、`text_align`、`text_filter: ["UP"]`、`text_family` (kfile:// または論理名。省略時はシステム既定フォント)、`text_size_type: "FIXED_WIDTH"` のとき text_size は**枠の幅**を意味し `text_lines` 行に折り返し
- アイコン: `icon_icon` に加え `icon_set` (例 `iconify://wi?name=Weather%20Icons`) が付随する。アイコンの検索元セット情報と見られるが未使用・未検証 (2026-07-20 sizuka_home で確認)
- 画像: `bitmap_bitmap` (kfile://...)、`bitmap_width`、`bitmap_alpha`。元画像の縦横比を維持して描画する。S041では保存された`bitmap_height`より元画像比率が正解だった
- コンポーネント: `internal_author_name/email`、`internal_description`、`internal_locked`、`config_scale_value` (拡大率と見られる、未検証)。中の `viewgroup_items` はレイヤーと同様に汎用描画されるため子要素自体は表示される
- 回転: `config_rotate_mode: "CLOCK_SECOND"` 等。秒・分・時針のサンプル時刻による回転を実装済み
- プログレス: `style_style: "CIRCLE"` + `style_size` (直径) + `style_height` (線幅)
- Stack: `config_stacking` ("HORIZONTAL_CENTER" 等、HORIZONTAL を含めば横並び。実例: HORIZONTAL_CENTER/HORIZONTAL_BOTTOM/VERTICAL_CENTER/VERTICAL_RIGHT)、`config_margin` (要素間隔)
- 可視制御: `config_visible: false`、`internal_toggles` (数式トグル)
- 動的な値: `internal_formulas` (プロパティを数式で上書き)、`internal_animations`、`internal_events` (タッチアクション)
- プロパティUIのアンカーは9方向の日本語プルダウンで表示し、`AnchorChoices` がKLWP内部値（`TOPLEFT`〜`BOTTOMRIGHT`）と双方向変換する
- `preset_root` 自体にも `position_padding_top` が付与されるケースがある (genoblanc で確認)。用途未検証
- `background_type` が省略されるプリセットも実在する (S041: background_color のみで type省略 / genoblanc: 背景関連キーが一切なし)。描画実装は省略時に "SOLID" とみなしており、実ファイルの意図と整合している

### アイコンの形式 (重要な発見)

`icon_icon` = `"アイコン名#<base64(gzip(SVG全文))>"`。
デコードすると viewBox 付き SVG が得られ、`d` 属性のパスを描画すれば
実アイコン (Discord/Twitter/カメラ等) をそのまま再現できる。

---

## 3. KLWP 座標系・配置ルール (最重要。実機照合で確定済み)

### 座標系

- **画面幅 = 常に 720 単位** (端末解像度に依存しない仮想単位)
- doc 高さ = `720 * 端末縦解像度 / 端末横解像度` (1080x2400 なら 1600)
- `preset_info` の width/height (540x1200 等) は**レイアウトに使ってはならない**

### 配置ルール

1. **アンカー未指定時のデフォルトは CENTER（中央）** (ルート・レイヤー内共通)
2. **ルート直下の要素**は `position_offset_x/y` をアンカーからの距離として
   使用する。左上アンカーの場合だけ見かけ上の絶対座標と一致するが、保存値は
   常にアンカー基準のオフセットであり、画面左上からのX/Y座標ではない。
3. **Overlap/Stack内の子要素**は四辺の `position_padding_*` を余白として
   使用する。左・上アンカーは左/上余白、右・下アンカーは右/下余白、中央系は
   両側の余白差の半分で配置する。余白は子要素を含むレイヤー寸法にも加算する。
4. プレビューでの移動・リサイズ・複製は、ルート要素ならオフセット、子要素なら
   四辺余白を更新する。子要素へ `position_offset_x/y` を新規作成しない。
5. ルートのTOP系はYオフセットの増加が下方向、CENTER/BOTTOM系は
   増加が上方向。アンカーキー未指定時はCENTER（中央）として扱う。
   配置・ドラッグ・リサイズ・プロパティUIで同じデフォルトを使用する
6. StackLayer の子は**順番に整列**し、四辺余白と `config_margin` を加味する
   (`HORIZONTAL_*` なら横、それ以外は縦)。
7. OverlapLayer 自体のサイズは明示されないため、全子要素のサイズと四辺余白を
   wrapした最大外寸を `_layer_box_size` で算出する。
8. FontIcon の既定 `icon_size` は **約80単位** (dock 実測から逆算)

※ ルートとレイヤー内で位置フィールドが異なる点は、追加・複製処理でも維持する。

---

## 4. 現行アプリの構造

```
klwp_editor.py              … 起動・後方互換ファサード
klwp/archive.py             … ZIP/JSON読書き、画像取込
klwp/background.py          … 背景数式・BITMAP Global紐付け
klwp/collections.py         … ArchiveContents
klwp/history.py             … ArchiveSnapshot / HistoryTimeline
klwp/values.py              … パス・文書サイズ・文字列・数値の値オブジェクト
klwp/formula.py             … Kodeトークン化・演算・関数評価
klwp/svg.py                 … SVGトークン列・曲線・円弧・マスク
klwp/resize.py              … リサイズハンドル判定・縦横比固定計算
klwp/preview/               … ページ推定、日付/global、Switch、animation
klwp/render/                … canvas、配置、合成、shape、text、content
klwp/ui/                    … 起動、文書操作、プロパティ、各設定ダイアログ
klwp/editor.py              … 上記Mixinを合成するEditorApp構成ルート
tools/check_object_calisthenics.py … 構造規約の静的検査
```

`EditorApp` のインスタンス状態は `ApplicationMemory` 1個に集約した。
アーカイブは `ArchiveContents`、Undo/Redoは `HistoryTimeline`、描画要求や
テキスト計測結果もファーストクラスコレクションで扱う。Tkinter・Pillow・
JSON/ZIPが要求するプリミティブ値は外部境界でのみ展開する。

Undo/Redoは最大50操作。`preset` はdeepcopy、変更されない `bytes` アセットは
辞書のみコピーして共有するため、大容量画像を操作ごとに複製しない。保存時点を
clean snapshotとして保持し、その地点までUndo/Redoすると未保存マークも連動する。

### リファクタリング規約

`python tools/check_object_calisthenics.py` と `test_architecture.py` が次を強制する。

- `else` / `elif` を使用しない（早期returnまたはディスパッチ）
- 1メソッドの制御構造ネストは1段、長さは30行以内、1クラスは250行以内
- 1クラスのインスタンス変数は2個以内
- property/getter/setterデコレータを使用しない
- 二段以上のメッセージ連鎖を使用しない

ドメイン標準の略語（KLWP、Kode、SVG、RGBA）とPython/Tkinter/Pillowの公式名
（`tk`、`ttk`等）は例外。それ以外の新規識別子は省略しない。

アニメーションプレビュー状態 (`preview_scroll`、`preview_switches` 等) は
presetへ保存しない。ルート要素の `internal_animations` を合成し、SCROLLの
`center/rule/speed/angle`、FADE、SWITCH_GLOBAL、LOOP_2Wを近似評価する。
描画時にイベント要素の再帰的boundsを `_event_regions` に記録するため、透明な
タップ判定Shapeも操作可能。Androidアプリ起動・音楽操作は表示だけで外部実行しない。

図形追加は `SHAPE_TYPE_OPTIONS` / `SHAPE_TYPE_SPECS` を正とする。図形一覧sampleで
正方形=`shape_type`省略、直角三角形=`RTRIANGLE`、六角形=`EXAGON`、
角丸四角形=`SQUIRCLE`を確認済み。弧型は同sampleに含まれないため`ARC`として実装。

描画パイプライン: RGBA キャンバスに背景 (cover-crop) → 各要素を再帰描画。
すりガラスは「領域切り出し→GaussianBlur→paint_color を 35% ブレンド→
角丸/パスマスクで paste」。CLIP_NEXT は次要素を透明レイヤーに描いて
マスク乗算合成。

## 5. プレビューの既知の近似・制限

- 数式の端末値はツールバーの「プレビュー値」で編集できる模擬値。
  `internal_formulas` / globalsとsample内の全関数を評価するが公式Kode全構文ではない
- OUTERグロー、線形／放射／Sweepグラデーション、主要blend modeは対応済み。
  AndroidのSkiaとPillowの画素差は残る
- SCROLL/SWITCH/LOOP_2Wで移動・FADE・ROTATE・SCALE・色フィルターを再現。
  直線・加速・減速・OVERSHOOT・BOUNCE easeに対応
- FIXED_WIDTH の折り返しは全角 1em 幅仮定の近似
  (高さは 2026-07-20 修正で実フォント計測になった。折り返し位置のみ近似が残る)
- Zen Kaku Gothic New.ttf はアーカイブ内で 0 バイト (破損)。
  日本語はシステムフォント (meiryo 等) にフォールバック
- Overlap/Komponentは全子要素からwrap領域を計算する。未知形式では近似誤差があり得る
- BitmapModuleはgenoblanc 3件とS041 1件を含め描画対応済み
- Komponentは`config_scale_value`で子描画・選択境界・タップ領域を一様拡縮する
- Shape/Textの固定回転と時計グループ回転は対応済み。任意の動的回転式は近似

### テキスト座標ズレの修正 (2026-07-20)

長らく残っていた「一部テキストの座標がずれる」問題を修正した。原因は
**計測と描画の条件不一致**の複合:

1. `_item_size` はインク bbox でサイズを測るのに、`_paint_text` は Pillow の
   テキスト原点 (ascent 上端) に描いていた → ascent 余白ぶん下にずれる (最大要因)
2. 計測は doc 単位サイズのフォント、描画は `size*scale` のフォントで、
   ヒンティングにより bbox が線形スケールしない
3. 複数行の行間が計測 (4px相当×scale) と描画 (固定4px) で不一致
4. FIXED_WIDTH の高さが `1.35em×行数` の決め打ちで、枠内 align 寄せも未実装

対策: `_text_layout(item)` ヘルパーを新設し、**描画とまったく同じ
フォントインスタンス・行間・align で計測**して結果をキャッシュ。
`_paint_text` は bbox 左上 (ベアリング) を差し引いて描くことで、インクの
左上が `_place` の計算位置に正確に一致する。FIXED_WIDTH は枠幅 =
`text_size` 固定とし、枠内で align に従って寄せる。
行間は `_TEXT_SPACING_U = 4.0` (doc単位) を計測・描画で共有 —
**変更時は必ず両方に効く `_text_layout` 経由を保つこと**。

検証: 5パターン (TOPLEFT/CENTER/BOTTOMRIGHT × 和文/欧文/複数行/FIXED_WIDTH)
でインクの実ピクセル bbox と `_place` 期待位置が誤差 3px 以内で一致することを
確認済み。残る誤差は字形サイドベアリングのメトリクス差 (Android 側も
メトリクス測位のため実害なし)。sample/ 全KLWPの描画回帰も通過。

## 6. テスト・検証方法

- 全テスト: `python -m unittest -v`（機能50件＋構造1件）
- 構造規約のみ: `python tools/check_object_calisthenics.py`
- Pillowヘッドレス描画: GUIを起動せず `render_to_image()` を呼び、全sampleを検証
- ラウンドトリップ: load → save → load で items/bitmaps 数と編集値を assert
- 描画検証: プレビューを PNG 出力し、実機スクショと**ピクセル座標で照合**
  (単位変換: `px = unit/720*幅`、`unit = px/1080*720`)。
  例: dock アイコン中心の実測 = 120/237/360/483/603 単位
- 配置ルールの検証に使った代表要素:
  時計すりガラス (TOPLEFT 405,135 / 275x310 / corners36 / BLURRED)、
  ひとこと (CENTER, offset -160,+320 → 上方向)、
  dock Stack (offset無視・センタリング)、
  天気パネル内テキスト (padding シフト)

## 7. 優先タスクの実施結果 (2026-07-21)

1. 完了: Komponent `config_scale_value` を内容・境界・イベント領域へ適用
2. 完了: 線形／放射／Sweepグラデーションと主要blend mode
3. 完了: Kodeの数学・文字列・色・正規表現拡張とプレビュー値編集UI
4. 完了: ROTATE/SCALE/色フィルターとease拡張
5. 完了: TEXT/NUMBER/COLOR/SWITCH/BITMAP/FONTグローバル編集UI
6. 完了: アプリ・ショートカット・URI・音楽・Kustomタッチ設定UI
7. 完了: 保存から `/sdcard/Kustom/wallpapers/` へのadbワンクリック転送
8. 完了: 公式v1/v3/v4/v5を追加し、v10/v11/v15と合わせて回帰検証

次の候補は、公式Kodeの未対応関数、Android 3.82 Shader、実機との
ピクセル差自動比較、ADB経由のアプリ／Activity選択支援である。

## 8. 開発方針・注意事項

- **未知のキーは保持する** (dict をそのまま持ち回り、編集キーのみ更新)。
  これにより KLWP 側で作った複雑な設定を壊さない
- 保存時は `preset_info.ts` を更新
- Android 側の読み込み: `内部ストレージ/Kustom/wallpapers/` に配置 →
  KLWP メニュー「読み込み」。保存/書き出しには KLWP Pro が必要
- 検証環境に日本語フォントがない場合、豆腐は環境要因であり
  Windows (meiryo) では正常表示される点に注意
