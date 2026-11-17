package com.kingzcheung.xime.ui.settings

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class CreditsTest {
    private val items = Credits.groups.flatMap { it.second }

    @Test fun everyItemOpensAnHttpsPage() {
        val bad = items.filterNot { it.url.startsWith("https://") }.map { it.name }
        assertTrue("不是 https 链接：$bad", bad.isEmpty())
    }

    @Test fun namesAreUnique() {
        assertEquals(items.size, items.map { it.name }.toSet().size)
    }

    /** 只将本发行版真实使用的来源列为随包资源，同时保留上游与设计参考署名。 */
    @Test fun namedSourcesAreListed() {
        val names = items.map { it.name }
        for (name in listOf("Xime", "CyIME", "雾凇拼音", "SCOWL", "CC-CEDICT", "Whisper", "MakeMeAHanzi 图形", "三星键盘", "Gboard", "首道双拼"))
            assertTrue("缺少 $name", name in names)
    }

    /** 设计参考只是参考，不写许可证；其余各项都要写。 */
    @Test fun onlyDesignReferencesHaveNoLicense() {
        Credits.groups.forEach { (group, list) ->
            list.forEach { assertEquals("$group / ${it.name}", group == "设计参考", it.license == null) }
        }
    }
}
