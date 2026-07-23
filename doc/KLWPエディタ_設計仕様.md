# KLWPエディタ 現行設計仕様

この文書は、現在の `klwp_editor.py` と `klwp/` パッケージを基準にした設計資料です。図はすべて Mermaid 形式で記述しています。

- 対象実装: 2026-07-22 時点
- 実行入口: `klwp_editor.py`
- 合成ルート: `klwp/editor.py` の `EditorApp`
- 永続化対象: ZIP 形式の `.klwp` ファイル
- 一時状態: `ApplicationMemory` に集約された、保存されない編集・プレビュー状態

## 1. 設計の全体像

`EditorApp` は、責務別の Mixin を組み合わせる合成ルートです。各 Mixin は状態を直接保持せず、`ApplicationMemory` を介して共同作業します。KLWP ファイルそのものは `KlwpArchive` が管理し、描画は Pillow 上で合成した後に Tk Canvas へ表示します。

| 領域 | 主な責務 | 主な実装場所 |
| --- | --- | --- |
| エントリーポイント | 実行条件の確認と GUI 起動 | `klwp_editor.py` |
| アプリケーション合成 | Mixin と `tk.Tk` の統合 | `klwp/editor.py` |
| ドキュメント | 新規、読込、保存、履歴、モジュール操作 | `klwp/ui/document.py` |
| UI | ウィンドウ、ツリー、プロパティ、設定ダイアログ | `klwp/ui/` |
| 描画 | Canvas、配置、合成、図形、文字、画像 | `klwp/render/` |
| プレビュー | 数式値、スイッチ、ページ、アニメーション | `klwp/preview/` |
| KLWP形式 | ZIP、`preset.json`、画像、フォント | `klwp/archive.py` |
| 値と状態 | 値オブジェクト、履歴、コレクション | `klwp/values.py` ほか |
| Kode/SVG | 数式評価、SVG Path の解析とマスク化 | `klwp/formula.py`, `klwp/svg.py` |
| Android転送 | adb検出、端末選択、保存済み成果物のpush | `klwp/adb.py`, `klwp/ui/adb_transfer.py` |

## 2. クラス図

### 2.1 EditorApp の合成

`EditorApp` 自身は起動定数とプロパティ定義だけを持ち、処理は Mixin に分散されています。`BootstrapMixin` が唯一のアプリケーション状態 `memory` を生成します。

```mermaid
classDiagram
    direction LR

    class TkRoot["tk.Tk"]
    class EditorApp {
        +CANVAS_W
        +CANVAS_H
        +HISTORY_LIMIT
        +PROP_FIELDS
    }
    class BootstrapMixin {
        +__init__()
        -_initialize_document_memory()
        -_initialize_preview_memory()
        -_initialize_history_memory()
    }
    class DocumentLifecycleMixin {
        +cmd_new()
        +cmd_open()
        +cmd_save()
    }
    class DocumentMixin {
        +cmd_undo()
        +cmd_redo()
        -_refresh_all()
    }
    class PreviewModelMixin {
        -_root_globals()
        -_value(item, key, default)
        -_animation_transform(item)
        -_reset_preview_state()
    }
    class CanvasRendererMixin {
        -_render()
        +render_to_image(width, height)
    }
    class LayoutMixin
    class CompositorLeafMixin
    class CompositorMixin
    class ShapeGeometryMixin
    class ShapeMaskMixin
    class GradientRendererMixin
    class ComponentRendererMixin
    class BlendRendererMixin
    class AnimationEffectMixin
    class ShapeRendererMixin
    class ContentRendererMixin
    class TextRendererMixin
    class PreviewInteractionMixin
    class ResizeInteractionMixin
    class InteractionMixin
    class ResizeHandleSet {
        +supports(item)
        +positions(bounds)
        +hit(bounds, horizontal, vertical, tolerance)
    }
    class ResizeSession {
        +apply(horizontal, vertical)
        +changed()
    }
    class PositionMutation {
        -_values
        +move_by(horizontal, vertical)
    }
    class SettingsMixin
    class PropertyPanelMixin
    class PreviewValuesMixin
    class AdbTransferMixin
    class TreeDragMixin {
        -_on_tree_press(event)
        -_on_tree_drag(event)
        -_on_tree_release(event)
    }
    class ApplicationMemory {
        -_values
        +optional(name, default)
        +contains(name)
    }
    class EditorWindowBuilder {
        -_owner
        +build()
    }

    TkRoot <|-- EditorApp
    BootstrapMixin <|-- EditorApp
    DocumentLifecycleMixin <|-- DocumentMixin
    DocumentMixin <|-- EditorApp
    PreviewModelMixin <|-- EditorApp
    CanvasRendererMixin <|-- EditorApp
    LayoutMixin <|-- EditorApp
    CompositorMixin <|-- EditorApp
    ShapeRendererMixin <|-- EditorApp
    ContentRendererMixin <|-- EditorApp
    TextRendererMixin <|-- EditorApp
    InteractionMixin <|-- EditorApp
    SettingsMixin <|-- EditorApp
    PropertyPanelMixin <|-- EditorApp
    PreviewValuesMixin <|-- EditorApp
    AdbTransferMixin <|-- EditorApp
    TreeDragMixin <|-- EditorApp

    CompositorLeafMixin <|-- CompositorMixin
    ShapeGeometryMixin <|-- ShapeRendererMixin
    ShapeMaskMixin <|-- ShapeRendererMixin
    PreviewInteractionMixin <|-- InteractionMixin
    ResizeInteractionMixin <|-- InteractionMixin
    ResizeInteractionMixin ..> ResizeHandleSet
    ResizeInteractionMixin ..> ResizeSession
    InteractionMixin ..> PositionMutation : drag
    ResizeInteractionMixin ..> PositionMutation : preserve opposite edge
    DocumentMixin ..> PositionMutation : duplicate shift
    CanvasRendererMixin ..> ResizeHandleSet : selection handles

    EditorApp *-- ApplicationMemory : memory
    BootstrapMixin ..> EditorWindowBuilder : builds
```

### 2.2 KLWPアーカイブ、値、履歴

`.klwp` は ZIP として扱われます。`ArchiveContents` は `preset.json`、ビットマップ、フォント、その他エントリー、ファイル位置をひとまとめにしたファーストクラスコレクションです。

画像エントリー名は `bitmaps/IMG` にUUIDの32桁hexを続けます。ZIPエントリーにはKLWP実機と同じUTF-8・data descriptorフラグ `0x808` を設定します。旧版で生成された28桁IDは、`BitmapReferenceNormalizer` が画像名と `preset.json` 内の参照を同時に32桁へ移行します。

```mermaid
classDiagram
    direction LR

    class ApplicationMemory {
        -_values
    }
    class KlwpArchive {
        +contents
        +load(path)
        +new(width, height, title)
        +save(path)
        +add_bitmap(path)
        +replace_bitmap(name, path)
        +root_module()
        +modules()
    }
    class ArchiveContents {
        -_entries
        +clear()
        +asset_groups()
    }
    class ArchiveReader {
        -_contents
        -_location
        +read()
    }
    class ArchiveWriter {
        -_contents
        -_location
        +write()
    }
    class BitmapImporter {
        -_contents
        -_location
        +add()
        +replace(name)
    }
    class BitmapReferenceNormalizer {
        -_contents
        +normalize()
    }
    class PresetFactory {
        +create(width, height, title)
    }
    class ArchiveClock {
        +timestamp()
    }
    class ArchiveLocation {
        -_value
        +__fspath__()
    }
    class DocumentSize {
        -_width
        -_height
        +json_fields()
    }
    class NumberValue {
        -_value
    }
    class TextValue {
        -_value
    }
    class HistoryTimeline {
        -_values
        +reset(snapshot)
        +record(snapshot)
        +undo()
        +redo()
        +saved(snapshot)
        +dirty()
    }
    class ArchiveSnapshot {
        -_values
    }

    ApplicationMemory o-- KlwpArchive : archive
    ApplicationMemory o-- HistoryTimeline : history
    KlwpArchive *-- ArchiveContents : owns
    KlwpArchive ..> ArchiveReader : load
    KlwpArchive ..> ArchiveWriter : save
    KlwpArchive ..> BitmapImporter : import bitmap
    KlwpArchive ..> BitmapReferenceNormalizer : load and save migration
    KlwpArchive ..> PresetFactory : new
    ArchiveReader --> ArchiveLocation
    ArchiveWriter --> ArchiveLocation
    BitmapImporter --> ArchiveLocation
    BitmapReferenceNormalizer --> ArchiveContents
    PresetFactory ..> DocumentSize
    PresetFactory ..> TextValue
    PresetFactory ..> ArchiveClock
    DocumentSize *-- NumberValue
    HistoryTimeline o-- ArchiveSnapshot : undo current redo clean
```

### 2.3 描画パイプライン

`CanvasRendererMixin` が描画全体を開始し、`CompositorMixin` がモジュールツリーを再帰的に合成します。値解決、アニメーション、配置計算を行った後、モジュール種別ごとのレンダラーへ振り分けます。ルート要素の `position_offset_x/y` はアンカーからの距離であり、左上からの絶対座標ではありません。Overlap/Stack内の子要素は四辺の `position_padding_*` を余白として配置し、端アンカーは対応する辺、中央系アンカーは両側余白の差の半分を使用します。アンカー未指定時はCENTER（中央）として扱います。

```mermaid
classDiagram
    direction LR

    class CanvasRendererMixin {
        -_render()
        +render_to_image(width, height)
        -_paint_background()
    }
    class CompositorLeafMixin {
        -_paint_item()
        -_paint_request()
        -_item_placement()
        -_paint_leaf()
    }
    class CompositorMixin {
        -_paint_children()
        -_paint_stack()
        -_paint_overlap()
    }
    class PaintRequest {
        -_values
    }
    class ItemPlacement {
        -_values
    }
    class StackCursor {
        -_horizontal
        -_vertical
    }
    class LayoutMixin {
        -_item_size()
        -_place()
        -_bounds()
    }
    class LayoutRequest {
        -_values
    }
    class PlacementCalculator {
        -_owner
        -_request
        +calculate()
    }
    class ModulePadding {
        -_values
    }
    class ShapeRendererMixin {
        -_paint_shape()
        -_paint_rotated_item()
    }
    class ShapeGeometryMixin
    class ShapeMaskMixin
    class TextRendererMixin {
        -_text_layout()
        -_paint_text()
    }
    class TextLayoutResult {
        -_values
    }
    class ContentRendererMixin {
        -_paint_bitmap()
        -_paint_icon()
        -_paint_progress()
    }
    class AnimationTransform {
        -_owner
        -_item
        +calculate()
    }
    class ModuleValueResolver {
        -_owner
        -_global_values
        +resolve(item, key, default)
    }
    class SvgPathParser {
        -_stream
        -_state
        +subpaths()
    }

    CanvasRendererMixin ..> CompositorLeafMixin : starts recursive paint
    CompositorLeafMixin <|-- CompositorMixin
    ComponentRendererMixin <|-- CompositorMixin
    BlendRendererMixin <|-- CompositorMixin
    AnimationEffectMixin <|-- CompositorMixin
    CompositorLeafMixin ..> PaintRequest
    CompositorLeafMixin ..> ItemPlacement
    CompositorMixin ..> StackCursor
    CompositorLeafMixin ..> LayoutMixin : size and position
    LayoutMixin ..> LayoutRequest
    LayoutMixin ..> PlacementCalculator
    PlacementCalculator *-- ModulePadding
    CompositorLeafMixin ..> AnimationTransform
    CompositorLeafMixin ..> ModuleValueResolver
    CompositorLeafMixin ..> ShapeRendererMixin : ShapeModule
    CompositorLeafMixin ..> TextRendererMixin : TextModule
    CompositorLeafMixin ..> ContentRendererMixin : bitmap icon progress
    ShapeGeometryMixin <|-- ShapeRendererMixin
    ShapeMaskMixin <|-- ShapeRendererMixin
    GradientRendererMixin <|-- ShapeRendererMixin
    TextRendererMixin ..> TextLayoutResult
    ShapeMaskMixin ..> SvgPathParser : Path shape
    ContentRendererMixin ..> SvgPathParser : icon path
```

### 2.4 プレビュー、アニメーション、Kode数式

プレビュー状態は KLWP アーカイブへ保存されません。現在ページ、スイッチの目標値と補間値、ループ開始時刻、タップ領域などは `ApplicationMemory` 内だけに存在します。

```mermaid
classDiagram
    direction LR

    class PreviewModelMixin {
        -_preview_page_count()
        -_animation_transform(item)
        -_root_globals()
        -_value(item, key, default)
    }
    class PreviewStateResetter {
        -_owner
        +reset()
    }
    class PreviewPageCounter {
        -_root_module
        -_pages
        +count()
    }
    class ScrollFadeRuleDetector {
        -_modules
        +has_triplet()
    }
    class RootGlobalValues {
        -_owner
        +values()
    }
    class PreviewDateValues {
        -_timestamp
        +values()
    }
    class ModuleValueResolver {
        -_owner
        -_global_values
        +resolve(item, key, default)
    }
    class AnimationTransform {
        -_owner
        -_item
        +calculate()
    }
    class TransformState {
        -_values
        +add_horizontal(distance)
        +add_vertical(distance)
        +multiply_alpha(value)
        +add_rotation(angle)
        +multiply_scale(scale)
        +apply_filter(name, amount)
        +result()
    }
    class AnimationEasing {
        +apply(progress)
    }
    class LoopProgress {
        -_started_at
        +for_animation(animation)
    }
    class FormulaParser {
        -_context
        +parse()
    }
    class FormulaContext {
        -_values
    }
    class FormulaTokenStream {
        -_tokens
        -_position
        +take()
        +peek(expected)
    }
    class FormulaTokenizer {
        +tokens(source)
    }
    class FormulaGlobals {
        -_values
    }
    class FormulaArguments {
        -_values
    }
    class FormulaFunctions {
        -_context
        +call(name, arguments)
    }
    class BinaryOperations {
        +apply(operator, left, right)
    }
    class PreviewFormulaValues
    class MathematicsUtilities
    class TextConversions
    class ColorEditor

    PreviewModelMixin ..> PreviewStateResetter
    PreviewModelMixin ..> PreviewPageCounter
    PreviewModelMixin ..> ScrollFadeRuleDetector
    PreviewModelMixin ..> RootGlobalValues
    PreviewModelMixin ..> ModuleValueResolver
    PreviewModelMixin ..> AnimationTransform
    RootGlobalValues ..> PreviewDateValues
    AnimationTransform *-- TransformState
    AnimationTransform ..> LoopProgress
    AnimationTransform ..> AnimationEasing
    ModuleValueResolver ..> FormulaParser : eval_formula
    FormulaParser *-- FormulaContext
    FormulaContext *-- FormulaTokenStream
    FormulaContext *-- FormulaGlobals
    FormulaTokenStream ..> FormulaTokenizer
    FormulaParser ..> FormulaArguments
    FormulaParser ..> FormulaFunctions
    FormulaParser ..> BinaryOperations
    FormulaFunctions ..> PreviewFormulaValues
    FormulaFunctions ..> MathematicsUtilities
    FormulaFunctions ..> TextConversions
    FormulaFunctions ..> ColorEditor
```

### 2.5 UIの協調クラス

UI クラスは `EditorApp` を owner として受け取り、処理が確定した時点で `DocumentMixin` または `PropertyPanelMixin` の更新処理へ戻します。

```mermaid
classDiagram
    direction LR

    class EditorApp
    class EditorWindowBuilder {
        +build()
    }
    class ModuleTreeBuilder {
        +build()
    }
    class ModuleTreePresentation {
        +title(item)
        +kind(item)
        +priority(index, count)
        +tags(item)
    }
    class TreeDragMixin
    class TreeReorder {
        +move(siblings, source, target, after)
    }
    class PropertyPanelBuilder {
        +build()
    }
    class AnchorChoices {
        +display_values()
        +to_display(internal_value)
        +to_internal(display_value)
    }
    class ColorControl {
        +build()
        +replace_color(value)
        +encoded_color()
    }
    class KlwpColor {
        +encoded()
        +chooser_color()
        +opacity_percentage()
        +replace_chooser_color(value)
        +replace_opacity_percentage(value)
    }
    class JsonEditorDialog {
        +show()
    }
    class ShapeDialog {
        +show()
    }
    class BackgroundDialog {
        +show()
    }
    class BackgroundImageBinding {
        +form_values()
        +apply(formula, global_name)
    }
    class BitmapGlobalCollection {
        +names()
        +add(name, reference)
        +contains(name)
    }
    class ImageManagerDialog {
        +show()
    }
    class GlobalManagerDialog {
        +show()
    }
    class GlobalEntryDialog {
        +show()
    }
    class PreviewValuesDialog {
        +show()
    }
    class AdbTransfer {
        +send()
        +destination()
    }
    class AdbLocator {
        +find()
    }
    class ModuleSettingListDialog {
        +show()
    }
    class AnimationFormDialog {
        +show()
    }
    class EventFormDialog {
        +show()
    }
    class SwitchReferenceCounter {
        +count(value)
    }

    EditorApp ..> EditorWindowBuilder : startup
    EditorApp ..> ModuleTreeBuilder : refresh tree
    ModuleTreeBuilder ..> ModuleTreePresentation : row values
    EditorApp ..> TreeDragMixin : layer ordering
    TreeDragMixin ..> TreeReorder : commit drop
    EditorApp ..> PropertyPanelBuilder : selected item
    PropertyPanelBuilder ..> AnchorChoices : anchor combobox conversion
    PropertyPanelBuilder ..> ColorControl : visual color editing
    ShapeDialog ..> ColorControl : creation color
    ColorControl *-- KlwpColor : AARRGGBB value
    EditorApp ..> JsonEditorDialog : raw JSON edit
    EditorApp ..> ShapeDialog : add shape
    EditorApp ..> BackgroundDialog : background
    BackgroundDialog ..> BackgroundImageBinding : formula and Global link
    BackgroundDialog ..> BitmapGlobalCollection : BITMAP Globals
    EditorApp ..> ImageManagerDialog : bitmap assets
    EditorApp ..> GlobalManagerDialog : all globals
    GlobalManagerDialog ..> GlobalEntryDialog : add or edit
    EditorApp ..> PreviewValuesDialog : formula preview inputs
    EditorApp ..> AdbTransfer : push preset
    AdbTransfer ..> AdbLocator : locate executable
    EditorApp ..> ModuleSettingListDialog : item settings
    ModuleSettingListDialog ..> AnimationFormDialog
    ModuleSettingListDialog ..> EventFormDialog
    GlobalManagerDialog ..> SwitchReferenceCounter : deletion guard
```

## 3. シーケンス図

### 3.1 アプリケーション起動

起動時は空の KLWP プリセットを生成し、UI 構築後にプレビュー状態と履歴を初期化して、最初の画面を描画します。

```mermaid
sequenceDiagram
    autonumber
    actor User as 利用者
    participant Main as klwp_editor.main
    participant Editor as EditorApp
    participant Memory as ApplicationMemory
    participant Archive as KlwpArchive
    participant Factory as PresetFactory
    participant Window as EditorWindowBuilder
    participant Preview as PreviewStateResetter
    participant History as HistoryTimeline

    User->>Main: アプリケーションを実行
    Main->>Editor: EditorApp()
    Editor->>Memory: ApplicationMemory()
    Editor->>Archive: KlwpArchive()
    Editor->>Archive: new()
    Archive->>Factory: create(1080, 2400, untitled)
    Factory-->>Archive: preset辞書
    Editor->>Memory: archive・キャッシュ・プレビュー状態を格納
    Editor->>History: HistoryTimeline(HISTORY_LIMIT)
    Editor->>Window: build()
    Window-->>Editor: Tkウィジェットをmemoryへ登録
    Editor->>Preview: reset()
    Preview->>Archive: root_module()
    Preview-->>Editor: ページ・スイッチ状態を初期化
    Editor->>History: reset(snapshot)
    Editor->>Editor: _refresh_all()
    Editor->>Editor: ツリー構築・描画・プロパティ構築
    Editor->>Editor: mainloop()
```

### 3.2 KLWPファイルを開いて描画する

読込後の描画では、最上位モジュールごとに値解決、アニメーション変換、配置、種別別描画、子要素の再帰処理を実行します。

```mermaid
sequenceDiagram
    autonumber
    actor User as 利用者
    participant Document as DocumentMixin
    participant Dialog as FileDialog
    participant Archive as KlwpArchive
    participant Reader as ArchiveReader
    participant Zip as ZIPファイル
    participant Preview as PreviewStateResetter
    participant History as HistoryTimeline
    participant Tree as ModuleTreeBuilder
    participant Canvas as CanvasRendererMixin
    participant Globals as RootGlobalValues
    participant Composite as CompositorMixin
    participant Values as ModuleValueResolver
    participant Animation as AnimationTransform
    participant Placement as PlacementCalculator
    participant Renderer as 種別別Renderer

    User->>Document: cmd_open()
    Document->>Dialog: askopenfilename()
    Dialog-->>Document: 選択パス
    Document->>Archive: load(path)
    Archive->>Reader: ArchiveReader(contents, location)
    Reader->>Zip: preset.json・bitmaps・fonts・extrasを読む
    Zip-->>Reader: ZIPエントリー
    Reader-->>Archive: ArchiveContentsを更新
    Archive-->>Document: 読込完了
    Document->>Preview: reset()
    Document->>History: reset(snapshot)
    Document->>Tree: build()
    Document->>Canvas: _render()
    Canvas->>Canvas: render_to_image(width, height)
    Canvas->>Globals: values()
    Globals-->>Canvas: global_values

    loop archive.modules() の各モジュール
        Canvas->>Composite: _paint_item(image, item, globals)
        Composite->>Values: resolve(item, property, default)
        Values-->>Composite: 数式・Global・直接値の優先順で返す
        Composite->>Animation: calculate()
        Animation-->>Composite: dx・dy・alpha・rotation・scale・filter
        Composite->>Placement: calculate()
        Placement-->>Composite: 描画位置と寸法
        Composite->>Renderer: 図形・文字・画像・アイコン・進捗を描画
        Composite->>Composite: 子モジュールを再帰描画
    end

    Canvas-->>Document: Pillow RGBA画像
    Document-->>User: Tk Canvasへプレビュー表示
```

### 3.3 プロパティ編集とUndo／Redo

履歴には差分ではなく、KLWP アーカイブのスナップショットを保存します。保存時点のスナップショットを `clean` とし、現在値との差で未保存状態を判定します。

```mermaid
sequenceDiagram
    autonumber
    actor User as 利用者
    participant Panel as PropertyPanelBuilder
    participant Property as PropertyPanelMixin
    participant Document as DocumentMixin
    participant Archive as KlwpArchive
    participant History as HistoryTimeline
    participant Preview as PreviewStateResetter
    participant Canvas as CanvasRendererMixin

    User->>Panel: プロパティ値を変更
    Panel->>Property: _apply_prop(key, variable)
    Property->>Archive: 選択モジュールの値を更新
    Property->>Property: _mark_dirty()
    Property->>Document: _snapshot_archive()
    Document-->>Property: ArchiveSnapshot
    Property->>History: record(snapshot)
    History->>History: currentをundoへ移動・redoを消去
    History-->>Property: dirty状態
    Property->>Canvas: _render()
    Canvas-->>User: 編集結果を表示

    alt Undo
        User->>Document: cmd_undo()
        Document->>History: undo()
        History-->>Document: 直前のArchiveSnapshot
    else Redo
        User->>Document: cmd_redo()
        Document->>History: redo()
        History-->>Document: 次のArchiveSnapshot
    end

    Document->>Archive: _restore_archive_snapshot(snapshot)
    Document->>Preview: reset()
    Document->>Canvas: _refresh_all()
    Canvas-->>User: 復元結果を表示
```

### 3.4 保存処理

`ArchiveWriter` は現在の `ArchiveContents` から `preset.json` とアセット群を ZIP 圧縮し、`.klwp` として書き出します。

```mermaid
sequenceDiagram
    autonumber
    actor User as 利用者
    participant Document as DocumentMixin
    participant Archive as KlwpArchive
    participant Clock as ArchiveClock
    participant Writer as ArchiveWriter
    participant Zip as ZIPバッファ
    participant File as KLWPファイル
    participant History as HistoryTimeline

    User->>Document: cmd_save() または cmd_save_as()
    Document->>Archive: save(path)
    Archive->>Clock: timestamp()
    Clock-->>Archive: 現在時刻
    Archive->>Writer: ArchiveWriter(contents, location)
    Writer->>Zip: preset.jsonをJSONとして格納
    Writer->>Zip: extras・fonts・bitmapsを格納
    Writer->>File: ZIPバッファを書き込む
    File-->>Writer: 完了
    Writer-->>Archive: pathを更新
    Archive-->>Document: 保存完了
    Document->>History: saved(snapshot)
    History->>History: currentとcleanを同一にする
    Document-->>User: 未保存マークを解除
```

### 3.5 タップによるスイッチアニメーション

描画時に `internal_events` を持つモジュールの領域を登録します。操作プレビューモードでタップすると、該当領域のイベントを実行し、スイッチ値を 300ms で補間します。Android アプリ起動など外部アクションはステータス表示だけで終了します。

```mermaid
sequenceDiagram
    autonumber
    actor User as 利用者
    participant Interaction as InteractionMixin
    participant Events as PreviewInteractionMixin
    participant Memory as ApplicationMemory
    participant Timer as Tk after timer
    participant Canvas as CanvasRendererMixin
    participant Transform as AnimationTransform

    Note over Canvas,Memory: 直前の描画でイベント領域を_event_regionsへ登録済み
    User->>Interaction: Canvasを押して離す
    Interaction->>Events: _trigger_tap_at(x, y)
    Events->>Memory: 座標に一致するイベント領域を検索
    Events->>Events: _perform_preview_event(event)

    alt SWITCH_GLOBAL
        Events->>Memory: スイッチ目標値を反転
        Events->>Memory: 0.30秒のtransitionを登録
        Events->>Timer: after(16ms, _animation_tick)
        loop transition完了まで
            Timer->>Events: _animation_tick()
            Events->>Memory: 補間済みswitch_progressを更新
            Events->>Canvas: _render()
            Canvas->>Transform: calculate()
            Transform->>Memory: switch_progressを参照
            Transform-->>Canvas: dx・dy・alpha・rotation・scale・filter
            Canvas-->>User: アニメーションフレーム
            Events->>Timer: 次の16msを予約
        end
    else LAUNCH_SHORTCUTのページ移動
        Events->>Memory: scroll transitionを登録
        Events->>Timer: after(16ms, _animation_tick)
    else Android外部アクション
        Events-->>User: PCプレビューでは省略した旨を表示
    end
```

### 3.6 横スワイプによるページ追従

ドラッグ中はポインタ移動量を Canvas 幅で割って連続的なページ位置へ変換します。指を離した後は最寄りページへ 250ms でスムーズに吸着します。

```mermaid
sequenceDiagram
    autonumber
    actor User as 利用者
    participant Interaction as InteractionMixin
    participant Preview as PreviewInteractionMixin
    participant Memory as ApplicationMemory
    participant Canvas as CanvasRendererMixin
    participant Transform as AnimationTransform
    participant Timer as Tk after timer

    User->>Interaction: press(event)
    Interaction->>Memory: 開始x・現在page・moved=falseを保存
    loop 横方向にdrag
        User->>Interaction: drag(event)
        Interaction->>Preview: _set_preview_scroll(page)
        Preview->>Memory: preview_scrollを更新
        Preview->>Canvas: _render()
        Canvas->>Transform: calculate()
        Transform->>Memory: preview_scrollを参照
        Transform-->>Canvas: スクロール連動変換
        Canvas-->>User: ドラッグへ追従したフレーム
    end
    User->>Interaction: release(event)
    Interaction->>Preview: _start_scroll_transition(round(page))
    Preview->>Memory: 0.25秒のtransitionを登録
    Preview->>Timer: after(16ms, _animation_tick)
    loop 吸着完了まで
        Timer->>Preview: _animation_tick()
        Preview->>Memory: smoothstep補間でpageを更新
        Preview->>Canvas: _render()
        Preview->>Timer: 必要なら次フレームを予約
    end
    Canvas-->>User: 最寄りページで停止
```

### 3.7 図形・画像の直接リサイズ

編集モードで選択したShapeまたはBitmapには8方向のハンドルを表示します。Shapeはドラッグした軸を個別に変更し、Bitmapはどのハンドルでも現在の縦横比を維持します。サイズ変更後は、ルート要素ならアンカー基準オフセット、レイヤー内の子要素なら四辺余白を補正し、ドラッグしていない反対側の縁を固定します。描画時に全モジュールの境界を記録するため、Overlap内の子要素も最前面から選択・リサイズできます。

```mermaid
sequenceDiagram
    autonumber
    actor User as 利用者
    participant Canvas as CanvasRendererMixin
    participant Interaction as ResizeInteractionMixin
    participant Handles as ResizeHandleSet
    participant Session as ResizeSession
    participant Position as PositionMutation
    participant Item as ShapeまたはBitmap
    participant History as HistoryTimeline

    Canvas->>Handles: positions(selected_bounds)
    Handles-->>Canvas: 8方向のハンドル座標
    Canvas-->>User: 選択枠とハンドルを表示
    User->>Interaction: 縁またはハンドルを押す
    Interaction->>Handles: hit(bounds, pointer, tolerance)
    Handles-->>Interaction: N・E・S・Wまたは四隅
    Interaction->>Session: ResizeSession(item, handle, bounds, base_size)
    loop ドラッグ中
        User->>Interaction: drag(pointer)
        Interaction->>Session: apply(pointer)
        alt ShapeModule
            Session->>Item: shape_widthとshape_heightを個別更新
        else BitmapModule
            Session->>Item: 比率を固定してbitmap_widthだけ更新
        end
        Interaction->>Position: move_by(反対側の縁との差分)
        alt ルート要素
            Position->>Item: アンカー基準オフセットを補正
        else レイヤー内の子要素
            Position->>Item: 四辺余白を補正
        end
        Interaction->>Canvas: _render()
        Canvas-->>User: サイズ変更へ追従
    end
    User->>Interaction: release()
    Interaction->>History: record(snapshot)
```

### 3.8 ADBによるAndroid端末への転送

転送コマンドは編集中のプリセットを先に保存し、PATHまたはAndroid SDKから`adb`を検出します。接続状態が`device`の端末が1台だけであることを確認してから、KLWPのwallpapersディレクトリを作成し、保存済み`.klwp`を転送します。

```mermaid
sequenceDiagram
    autonumber
    actor User as 利用者
    participant Editor as AdbTransferMixin
    participant Document as DocumentMixin
    participant Locator as AdbLocator
    participant Transfer as AdbTransfer
    participant Adb as adb
    participant Android as Android端末

    User->>Editor: Androidへ転送
    Editor->>Document: cmd_save()
    Document-->>Editor: 保存済みファイルパス
    Editor->>Locator: find()
    Locator-->>Editor: adb実行ファイル
    Editor->>Transfer: AdbTransfer(adb, path)
    Editor->>Transfer: send()
    Transfer->>Adb: devices
    Adb-->>Transfer: 接続端末一覧
    Transfer->>Transfer: require_one(output)
    Transfer->>Adb: shell mkdir -p /sdcard/Kustom/wallpapers
    Adb->>Android: 転送先を準備
    Transfer->>Adb: push source destination
    Adb->>Android: .klwpを書き込み
    Transfer-->>Editor: device, destination
    Editor-->>User: 転送結果を表示
```

### 3.9 要素ツリーのドラッグによる表示優先度変更

ツリーはKLWPの配列順と同じく上から背面、下ほど前面として表示します。ドラッグ元とドロップ先が同じ兄弟コレクションに属する場合だけ、対象行の前または後へ移動します。別レイヤーへのドロップは階層構造を変えてしまうため受け付けません。変更はドロップ時に一度だけ履歴へ記録され、Undo/Redoできます。

子要素を持つレイヤーが選択中の場合、新規要素の追加先はそのレイヤーです。「選択解除（ルート）」ボタン、ツリーの空白クリック、またはEscキーで選択を解除すると、`selected` とTreeviewの選択を同時に消去し、以降の追加先をルートの `modules` へ戻します。選択解除自体は成果物を変更しないため履歴には記録しません。

```mermaid
sequenceDiagram
    autonumber
    actor User as 利用者
    participant Tree as Treeview
    participant Drag as TreeDragMixin
    participant Reorder as TreeReorder
    participant Items as viewgroup_items
    participant History as HistoryTimeline
    participant Preview as CanvasRendererMixin

    User->>Tree: 要素行を押してドラッグ
    Tree->>Drag: _on_tree_press / _on_tree_drag
    Drag->>Drag: 同じ兄弟コレクションか検証
    alt 有効なドロップ先
        Drag->>Tree: 前／後の候補行を色表示
        Drag-->>User: 前面側／背面側をステータス表示
    else 別レイヤーまたは空白
        Drag-->>User: 同一レイヤー内へのドロップを案内
    end
    User->>Tree: ドロップ
    Tree->>Drag: _on_tree_release
    Drag->>Reorder: move(siblings, source, target, after)
    Reorder->>Items: removeして対象位置へinsert
    Drag->>History: record(snapshot)
    Drag->>Preview: _refresh_all(select=source)
    Preview-->>User: 新しい重なり順を描画
```

### 3.10 数式・BITMAP Globalによる背景切替

背景設定は固定画像に加え、`internal_globals.background_bitmap` のBITMAP型Globalリンクと、`internal_formulas.background_bitmap` のKode数式を編集します。数式がある場合は数式、次にGlobalリンク、最後に固定の `background_bitmap` という通常の値解決優先順位を使用します。プレビュー値で日時を変更すると `df(H)` などが再評価され、Globalに保存されたアーカイブ内画像パスから背景を再描画します。

```mermaid
sequenceDiagram
    autonumber
    actor User as 利用者
    participant Dialog as BackgroundDialog
    participant Binding as BackgroundImageBinding
    participant Globals as BitmapGlobalCollection
    participant Archive as KlwpArchive
    participant Preview as PreviewValuesDialog
    participant Canvas as CanvasRendererMixin
    participant Resolver as ModuleValueResolver
    participant Formula as FormulaFunctions

    User->>Dialog: 背景設定を開く
    Dialog->>Binding: form_values()
    Binding-->>Dialog: 背景数式とGlobalリンク
    Dialog->>Globals: names()
    Globals-->>Dialog: BITMAP型Global一覧
    opt 背景用画像Globalを追加
        User->>Dialog: 画像ファイルと識別名を指定
        Dialog->>Archive: add_bitmap(path)
        Archive-->>Dialog: kfile参照
        Dialog->>Globals: add(name, reference)
    end
    User->>Dialog: 数式・Globalリンクを適用
    Dialog->>Binding: apply(formula, global_name)
    User->>Preview: プレビュー日時を変更
    Preview->>Canvas: 再描画
    Canvas->>Resolver: resolve(root, background_bitmap)
    Resolver->>Formula: eval background formula
    Formula->>Globals: gv(name)のvalueを解決
    Globals-->>Formula: kfile画像パス
    Formula-->>Resolver: 時間帯に対応する画像パス
    Resolver-->>Canvas: background_bitmap参照
    Canvas->>Archive: bitmaps/IMG...を読み込み
    Canvas-->>User: 切替後の背景を表示
```

## 4. 状態とデータの境界

### 4.1 `ApplicationMemory` の主な内容

| 分類 | キーの例 | 保存対象 |
| --- | --- | --- |
| ドキュメント | `archive`, `device_res`, `selected` | `archive` の内容だけ `.klwp` に保存 |
| 履歴 | `history`, `dirty` | 保存しない |
| UI | `tree`, `canvas`, `status`, 各ボタン | 保存しない |
| キャッシュ | `photo_cache`, `font_cache`, `_photo`, `_item_bounds` | 保存しない |
| 編集操作 | `drag_state`, `resize_state`, `tree_drag` | 保存しない |
| プレビュー | `preview_scroll`, `preview_switches`, `preview_switch_progress`, `preview_values`, `preview_ts` | 保存しない |
| アニメーション | `_switch_transitions`, `_scroll_transition`, `_loop_started_at` | 保存しない |
| イベント | `_event_regions`, `interaction_drag` | 保存しない |

### 4.2 KLWP値の解決優先順位

`ModuleValueResolver` は、描画プロパティを次の順序で解決します。

1. `internal_formulas[key]` にある Kode 数式
2. `internal_globals[key]` が参照する Global 値または Global 数式
3. モジュール自身の `item[key]`
4. 呼出側が指定した既定値

### 4.3 モジュール描画の振り分け

| `internal_type` | 主な描画先 |
| --- | --- |
| `ShapeModule` | `ShapeRendererMixin` |
| `TextModule` | `TextRendererMixin` |
| `FontIconModule` | `ContentRendererMixin._paint_icon()` |
| `BitmapModule` | `ContentRendererMixin._paint_bitmap()` |
| `KomponentModule` | `ComponentRendererMixin`（`config_scale_value` を適用して再帰合成） |
| `ProgressModule` | `ContentRendererMixin._paint_progress()` |
| `StackLayerModule` | `CompositorMixin._paint_stack()` |
| `OverlapLayerModule` など子要素を持つもの | `CompositorMixin._paint_overlap()` |

## 5. 保守時の更新指針

- `EditorApp` の継承 Mixin を追加・削除した場合は「2.1 EditorApp の合成」を更新する。
- KLWP ZIP の格納項目を変更した場合は「2.2」と「3.4」を更新する。
- 描画順、値解決順、子要素の合成方法を変更した場合は「2.3」と「3.2」を更新する。
- 新しいアニメーション反応・アクションを追加した場合は「2.4」「3.5」「3.6」を更新する。
- リサイズ対象・ハンドル・比率制約を変更した場合は「2.1」と「3.7」を更新する。
- 要素ツリーの順序・ドロップ制約を変更した場合は「2.5」と「3.9」を更新する。
- `ApplicationMemory` の状態分類を増やした場合は「4.1」を更新する。
- Mermaid 図のクラス名とメソッド名は、コード上の識別子と一致させる。
