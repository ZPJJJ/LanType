-- Tapped pairs arrive as capitals, individually selected letters as lowercase.
-- Query the same table in both cases. Only the selected letters constrain the spelling.
local keymap = "ABCDEDGGUJJlmBOOQEATUCQZTZ"
local function init(env)
    env.words = Component.Translator(env.engine, "", "t9_english_translator@k14_english")
end

-- For B站 and aliases such as brand abbreviations the displayed text does not spell its code.
-- The build exports only these exceptions alongside the same dictionary.
local aliases
local function aliases_for(text)
    if not aliases then
        aliases = {}
        local name = "/cyime_k14_aliases.tsv"
        local f = io.open(rime_api.get_shared_data_dir() .. name, "r") or io.open(rime_api.get_user_data_dir() .. name, "r")
        if f then
            for row in f:lines() do
                local word, spelling = row:match("^([^\t]+)\t([a-z]+)")
                if word then
                    aliases[word] = aliases[word] or {}
                    table.insert(aliases[word], spelling)
                end
            end
            f:close()
        end
    end
    return aliases[text]
end

local function fits(spelling, input, completion)
    if #spelling < #input or (not completion and #spelling ~= #input) then return false end
    for i = 1, #input do
        local key, letter = input:sub(i, i), spelling:sub(i, i)
        local index = letter:byte() - 96
        if key ~= letter and key ~= keymap:sub(index, index) then return false end
    end
    return true
end

local function translate(input, seg, env)
    if not input:match("^[a-zQETUOADGJZCB]+$") then return end
    local code = input:gsub("%l", function(c)
        local i = c:byte() - 96
        return keymap:sub(i, i)
    end)
    local words = env.words:query(code, seg)
    if not words then return end
    for cand in words:iter() do
        if input == code then
            yield(cand)
        else
            local spelling = cand.text:lower():gsub("[^a-z]", "")
            local completion = cand.type == "completion"
            local matches = fits(spelling, input, completion)
            if not matches then
                for _, alias in ipairs(aliases_for(cand.text) or {}) do
                    if fits(alias, input, completion) then matches = true; break end
                end
            end
            if matches then yield(cand) end
        end
    end
end

-- The native candidate policy reserves slots for Chinese words. If an English completion
-- already occupies an earlier slot, exchange the English slots so the fully typed word leads.
local function whole_words(input, env)
    local code = env.engine.context.input
    local first
    for cand in input:iter() do
        if #code >= 4 and cand.type == "completion" and cand.start == 0 and cand._end == #code
            and cand.text:match("^[A-Za-z]") then
            first = cand
            break
        end
        yield(cand)
    end
    if not first then return end
    local head, slots = {first}, {1}
    -- At most three English completions, and the native policy normally puts the word sixth.
    for cand in input:iter() do
        head[#head + 1] = cand
        if cand.start == 0 and cand._end == #code and cand.text:match("^[A-Za-z][A-Za-z '%-]*$") then
            if cand.type == "completion" then
                slots[#slots + 1] = #head
            elseif cand.type == "table" or cand.type == "user_table" then
                local place = #head
                for i = #slots, 1, -1 do
                    head[place] = head[slots[i]]
                    place = slots[i]
                end
                head[place] = cand
                break
            end
        end
        if #head >= 12 then break end
    end
    for _, cand in ipairs(head) do yield(cand) end
    for cand in input:iter() do yield(cand) end
end

return { init = init, func = translate, whole_words = whole_words }
