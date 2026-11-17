package app.lantype.testhost;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.os.Bundle;
import android.os.SystemClock;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.util.LinkedHashMap;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import org.json.JSONArray;
import org.json.JSONObject;

/** Disposable native editors for exercising the real, separately installed IME. */
public final class EditorActivity extends Activity {
    private final LinkedHashMap<String, EditText> editors = new LinkedHashMap<>();
    private EditText current;
    private String currentName = "Text A";
    private TextView status;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(dp(8), dp(8), dp(8), dp(4));
        TextView title = new TextView(this);
        title.setText("LanType QA Host — fictional text only");
        title.setTextSize(16);
        page.addView(title);

        addButtons(page, new String[] {"Text A", "Text B", "Password"}, this::showEditor);
        addButtons(page, new String[] {"Email", "Number", "Clear"}, label -> {
            if (label.equals("Clear")) {
                current.setText("");
                focusEditor();
            } else showEditor(label);
        });
        addButtons(page, new String[] {"Select all", "Mask sample", "Clipboard", "Inspect"}, label -> {
            if (label.equals("Inspect")) {
                inspectSyntheticClipboard();
                return;
            } else if (label.equals("Select all")) {
                current.setSelection(0, current.length());
            } else if (label.equals("Mask sample")) {
                showEditor("Text A");
                current.setText("Contact demo@example.test; phone 13800138000");
                current.setSelection(0, current.length());
            } else {
                ClipboardManager manager = getSystemService(ClipboardManager.class);
                manager.setPrimaryClip(ClipData.newPlainText("LanType synthetic QA", "fixture {{date}}"));
            }
            focusEditor();
        });
        status = new TextView(this);
        status.setId(R.id.editor_status);
        status.setTextSize(12);
        page.addView(status);

        addEditor(page, "Text A", R.id.editor_a,
            InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        addEditor(page, "Text B", R.id.editor_b,
            InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        addEditor(page, "Password", R.id.editor_password,
            InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        addEditor(page, "Email", R.id.editor_email,
            InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
        addEditor(page, "Number", R.id.editor_number,
            InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_SIGNED | InputType.TYPE_NUMBER_FLAG_DECIMAL);
        setContentView(page);
        String restored = state == null ? null : state.getString("editor");
        showEditor(editors.containsKey(restored) ? restored : "Text A");
    }

    private void addButtons(LinearLayout page, String[] labels, ButtonAction action) {
        LinearLayout row = new LinearLayout(this);
        for (String label : labels) {
            Button button = new Button(this);
            button.setText(label);
            button.setTextSize(12);
            button.setAllCaps(false);
            button.setMinWidth(0);
            button.setOnClickListener(view -> action.run(label));
            row.addView(button, new LinearLayout.LayoutParams(0, dp(44), 1));
        }
        page.addView(row, new LinearLayout.LayoutParams(-1, dp(44)));
    }

    private void addEditor(LinearLayout page, String name, int id, int inputType) {
        EditText editor = new EditText(this) {
            @Override protected void onSelectionChanged(int start, int end) {
                super.onSelectionChanged(start, end);
                if (current == this) updateStatus();
            }
        };
        editor.setId(id);
        editor.setHint(name);
        editor.setContentDescription(name + " editor");
        editor.setInputType(inputType);
        editor.setTextSize(18);
        editor.setGravity(android.view.Gravity.TOP | android.view.Gravity.START);
        editor.setVisibility(View.GONE);
        editor.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) { updateStatus(); }
            @Override public void afterTextChanged(Editable text) {}
        });
        editors.put(name, editor);
        page.addView(editor, new LinearLayout.LayoutParams(-1, dp(100)));
    }

    private void showEditor(String name) {
        if (current != null) current.clearFocus();
        for (EditText editor : editors.values()) editor.setVisibility(View.GONE);
        currentName = name;
        current = editors.get(name);
        current.setVisibility(View.VISIBLE);
        updateStatus();
        focusEditor();
    }

    private void focusEditor() {
        current.requestFocus();
        current.post(() -> getSystemService(InputMethodManager.class)
            .showSoftInput(current, InputMethodManager.SHOW_IMPLICIT));
    }

    /** Explicit, foreground, read-only probe. Never writes a clip or stores/logs arbitrary text. */
    private void inspectSyntheticClipboard() {
        JSONObject result = new JSONObject();
        try {
            ClipboardManager manager = getSystemService(ClipboardManager.class);
            ClipData clip = manager.getPrimaryClip();
            CharSequence value = clip != null && clip.getItemCount() == 1
                ? clip.getItemAt(0).getText() : null;
            String text = value == null ? null : value.toString();
            String fixture = null;
            if ("Debug.Log(\"{{cursor}}\"); // {{date}}".equals(text)) fixture = "csharp";
            else if ("print(\"{{cursor}}\") -- {{date}}".equals(text)) fixture = "lua";
            else if ("fixture {{date}}".equals(text)) fixture = "normal_before";
            else if ("Contact demo@example.test; phone 13800138000".equals(text)) fixture = "normal_after";
            if (fixture == null) {
                // No unknown body, hash, label, timestamp or extras reach the UI/evidence.
                result.put("error", "not_a_recognized_synthetic_fixture");
            } else {
                android.content.ClipDescription description = clip.getDescription();
                android.os.PersistableBundle extras = description.getExtras();
                byte[] digest = MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8));
                StringBuilder hex = new StringBuilder();
                for (byte part : digest) hex.append(String.format(java.util.Locale.ROOT, "%02x", part & 0xff));
                JSONArray mimes = new JSONArray();
                for (int index = 0; index < description.getMimeTypeCount(); index++)
                    mimes.put(description.getMimeType(index));
                result.put("fixture", fixture);
                result.put("text_sha256", hex.toString());
                result.put("utf16_length", text.length());
                result.put("item_count", clip.getItemCount());
                result.put("timestamp_ms", description.getTimestamp());
                result.put("label", description.getLabel() == null ? JSONObject.NULL : description.getLabel().toString());
                result.put("mime_types", mimes);
                result.put("tool_cabin_private", extras != null && extras.getBoolean("lantype.tool_cabin_private", false));
                result.put("sensitive", extras != null && extras.getBoolean("android.content.extra.IS_SENSITIVE", false));
                result.put("observed_at_epoch_ms", System.currentTimeMillis());
                result.put("observed_at_elapsed_ms", SystemClock.elapsedRealtime());
            }
        } catch (Exception error) {
            result = new JSONObject();
            try { result.put("error", "clipboard_inspection_unavailable"); }
            catch (org.json.JSONException ignored) { /* Fixed literal cannot fail. */ }
        }
        new AlertDialog.Builder(this)
            .setTitle("Clipboard fixture metadata")
            .setMessage(result.toString())
            .setPositiveButton("Done", (dialog, which) -> focusEditor())
            .setCancelable(false)
            .show();
    }

    private void updateStatus() {
        if (current == null || status == null) return;
        status.setText(currentName + " | UTF-16 length=" + current.length()
            + " | selection=" + current.getSelectionStart() + ".." + current.getSelectionEnd());
    }

    @Override protected void onSaveInstanceState(Bundle out) {
        out.putString("editor", currentName);
        super.onSaveInstanceState(out);
    }

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    private interface ButtonAction { void run(String label); }
}
