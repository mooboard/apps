"""Original jetpack runner expressed entirely in game ABI 1 assembly."""
import json
from pathlib import Path
from game_examples import Assembly, reset, pause_logic, hud


class A(Assembly):
    def field(self, register, offset):
        return self.put(23, offset).op("add", 23, 24, 23).op("loadi", register, 23)
    def save(self, register, offset):
        return self.put(23, offset).op("add", 23, 24, 23).op("storei", 23, register)
    def branchreg(self, lhs, comparison, rhs, label):
        return self.put(22, rhs).op(comparison, 22, lhs, 22).op("jnz", 22, label)


def source():
    # y, velocity, score, coins, lives, clock, immunity, pause, speed,
    # shield, coin flash, damage count, passed hazards, picked-up coins.
    memory = [1500, 0, 0, 0, 3, 0, 0, 0, 8, 0, 0, 0, 0, 0] + [0] * 114
    for i in range(3):
        memory[64+i*6:70+i*6] = [1180+i*1000, 7 if i % 2 == 0 else 20, i, 0, 0, 0]
    for i in range(8): memory[96+i*4:100+i*4] = [650+i*190, 10+(i % 4)*4, 1, int(i == 7)]
    init = A(); reset(init, memory)
    s = A(); pause_logic(s, memory, 7)
    s.add(5, 1)
    for slot in (6, 9, 10):
        s.branch(slot, "eq", 0, f"timer_{slot}").add(slot, -1).label(f"timer_{slot}")
    s.put(0, ("m", 5)).put(1, 5).op("mod", 0, 0, 1).op("jnz", 0, "score_done").add(2, 1).label("score_done")
    s.op("setting", 0, 0).put(1, 2).op("mul", 0, 0, 1).put(1, 6).op("add", 0, 0, 1)
    s.put(1, ("m", 2)).put(2, 300).op("div", 1, 1, 2).branchreg(1, "lt", 7, "level_ok").put(1, 6).label("level_ok")
    s.op("add", 0, 0, 1).op("store", 0, 8)
    s.op("input", 0, 0).op("input", 1, 1).op("or", 0, 0, 1).put(1, 17).op("and", 0, 0, 1).op("jz", 0, "gravity")
    s.add(1, -9).op("jump", "velocity").label("gravity").add(1, 6)
    s.label("velocity").branch(1, "lt", -70, "fast_up").branch(1, "lt", 71, "position").set(1, 70).op("jump", "position")
    s.label("fast_up").set(1, -70)
    s.label("position").add(0, ("m", 1)).branch(0, "lt", 700, "ceiling").branch(0, "lt", 2301, "objects")
    s.set(0, 2300).set(1, 0).op("jump", "objects").label("ceiling").set(0, 700).set(1, 0)
    s.label("objects").put(25, 0).label("hazards")
    s.put(24, 6).op("mul", 24, 25, 24).put(23, 64).op("add", 24, 24, 23)
    s.field(0, 0).put(1, ("m", 8)).op("sub", 0, 0, 1).field(2, 2).branchreg(2, "eq", 2, "missile_fast").op("jump", "hazard_moved")
    s.label("missile_fast").put(1, 7).op("sub", 0, 0, 1)
    s.label("hazard_moved").save(0, 0).branchreg(0, "lt", -200, "spawn_hazard")
    # A missile locks its height before entering; the warning has time to show.
    s.branchreg(2, "eq", 2, "missile_lock").op("jump", "hit_test")
    s.label("missile_lock").field(3, 3).op("jnz", 3, "hit_test").branchreg(0, "lt", 1700, "lock_now").op("jump", "hit_test")
    s.label("lock_now").put(3, ("m", 0)).put(4, 100).op("div", 3, 3, 4).put(4, 3).op("add", 3, 3, 4).save(3, 1).put(3, 1).save(3, 3)
    s.label("hit_test").branch(6, "eq", 0, "check_overlap").op("jump", "next_hazard")
    s.label("check_overlap").put(8, 19).put(9, ("m", 0)).put(10, 100).op("div", 9, 9, 10).put(10, 1).op("add", 9, 9, 10)
    s.put(10, 4).put(11, 6).put(12, 10).op("div", 12, 0, 12).field(13, 1).put(14, 3).put(15, 10)
    s.branchreg(2, "eq", 0, "box_ready").put(14, 15).put(15, 2).branchreg(2, "eq", 1, "box_ready").put(14, 8).put(15, 3)
    s.label("box_ready").op("overlap", 8).op("jz", 8, "next_hazard")
    s.branch(9, "eq", 0, "damage").set(9, 0).set(6, 45).op("jump", "next_hazard")
    s.label("damage").add(4, -1).add(11, 1).set(6, 75).branch(4, "eq", 0, "over").op("jump", "next_hazard")
    s.label("over").set(7, 110).op("jump", "next_hazard")
    s.label("spawn_hazard").add(12, 1).put(0, 600).op("random", 0, 0).put(1, 2850).op("add", 0, 0, 1).save(0, 0)
    s.put(0, 3).op("random", 0, 0).save(0, 2).put(0, 2).op("random", 0, 0).put(1, 13).op("mul", 0, 0, 1).put(1, 7).op("add", 0, 0, 1).save(0, 1)
    s.put(0, 0).save(0, 3)
    s.label("next_hazard").put(0, 1).op("add", 25, 25, 0).branchreg(25, "lt", 3, "hazards")
    s.put(25, 0).label("coins").put(24, 4).op("mul", 24, 25, 24).put(23, 96).op("add", 24, 24, 23)
    s.field(0, 0).put(1, ("m", 8)).op("sub", 0, 0, 1).save(0, 0).branchreg(0, "lt", -30, "respawn_coin")
    s.field(1, 2).op("jz", 1, "next_coin")
    s.put(8, 18).put(9, ("m", 0)).put(10, 100).op("div", 9, 9, 10).put(10, 7).put(11, 8)
    s.put(12, 10).op("div", 12, 0, 12).field(13, 1).put(14, 3).put(15, 3).op("overlap", 8).op("jz", 8, "next_coin")
    s.put(0, 0).save(0, 2).add(3, 1).add(13, 1).add(2, 10).set(10, 12)
    s.field(0, 3).op("jz", 0, "next_coin").set(9, 250).add(2, 40).op("jump", "next_coin")
    s.label("respawn_coin").put(0, 1550).save(0, 0).put(0, 1).save(0, 2)
    s.put(0, 15).op("random", 0, 0).put(1, 9).op("add", 0, 0, 1).save(0, 1)
    s.label("next_coin").put(0, 1).op("add", 25, 25, 0).branchreg(25, "lt", 8, "coins").op("halt")
    d = A().put(0, 0).op("clear", 0).rect(1, 7, 126, 24, 4)
    # Laboratory windows, lights and conveyor tiles move at different rates.
    d.put(25, 0).label("windows").put(16, 36).op("mul", 16, 25, 16).put(17, ("m", 5)).put(18, 4).op("div", 17, 17, 18).put(18, 36).op("mod", 17, 17, 18).op("sub", 16, 16, 17)
    d.rect(("r", 16), 9, 19, 16, 6).put(17, 2).op("add", 16, 16, 17).rect(("r", 16), 11, 15, 10, 12).rect(("r", 16), 24, 15, 1, 10)
    d.put(0, 1).op("add", 25, 25, 0).branchreg(25, "lt", 5, "windows")
    d.rect(1, 30, 126, 1, 10).put(25, 0).label("floor").put(16, 16).op("mul", 16, 25, 16).put(17, ("m", 5)).put(18, 16).op("mod", 17, 17, 18).op("sub", 16, 16, 17)
    d.rect(("r", 16), 30, 6, 1, 3).put(0, 1).op("add", 25, 25, 0).branchreg(25, "lt", 9, "floor")
    d.put(25, 0).label("draw_coins").put(24, 4).op("mul", 24, 25, 24).put(23, 96).op("add", 24, 24, 23)
    d.field(0, 2).op("jz", 0, "coin_next").field(16, 0).put(17, 10).op("div", 16, 16, 17).field(18, 1).field(19, 3)
    d.branchreg(19, "eq", 1, "orb").sprite(("r", 16), ("r", 18), 2).op("jump", "coin_next").label("orb").sprite(("r", 16), ("r", 18), 3)
    d.label("coin_next").put(0, 1).op("add", 25, 25, 0).branchreg(25, "lt", 8, "draw_coins")
    d.put(25, 0).label("draw_hazards").put(24, 6).op("mul", 24, 25, 24).put(23, 64).op("add", 24, 24, 23)
    d.field(16, 0).put(17, 10).op("div", 16, 16, 17).field(18, 1).field(19, 2)
    d.branchreg(19, "eq", 2, "rocket").branchreg(19, "eq", 1, "horizontal")
    d.rect(("r", 16), ("r", 18), 3, 10, 2).put(17, 1).op("add", 16, 16, 17).rect(("r", 16), ("r", 18), 1, 10, 5).op("jump", "hazard_next")
    d.label("horizontal").rect(("r", 16), ("r", 18), 15, 2, 8).put(17, 1).op("sub", 16, 16, 17).sprite(("r", 16), ("r", 18), 5).op("jump", "hazard_next")
    d.label("rocket").branchreg(16, "lt", 128, "draw_rocket").branchreg(16, "lt", 170, "warning").op("jump", "hazard_next")
    d.label("warning").put(17, ("m", 5)).put(19, 6).op("div", 17, 17, 19).put(19, 2).op("mod", 17, 17, 19).op("jz", 17, "hazard_next").sprite(118, ("r", 18), 6).op("jump", "hazard_next")
    d.label("draw_rocket").sprite(("r", 16), ("r", 18), 4)
    d.label("hazard_next").put(0, 1).op("add", 25, 25, 0).branchreg(25, "lt", 3, "draw_hazards")
    d.put(18, ("m", 0)).put(17, 100).op("div", 18, 18, 17)
    d.branch(6, "eq", 0, "hero").put(17, ("m", 5)).put(19, 4).op("div", 17, 17, 19).put(19, 2).op("mod", 17, 17, 19).op("jz", 17, "hud")
    d.label("hero").sprite(17, ("r", 18), 0)
    d.op("input", 17, 0).put(19, 17).op("and", 17, 17, 19).op("jz", 17, "shield")
    d.put(17, 4).op("add", 18, 18, 17).sprite(14, ("r", 18), 1).put(17, 4).op("sub", 18, 18, 17)
    d.label("shield").branch(9, "eq", 0, "hud").put(17, 1).op("sub", 18, 18, 17).rect(16, ("r", 18), 9, 1, 8).put(17, 8).op("add", 18, 18, 17).rect(16, ("r", 18), 9, 1, 8)
    d.label("hud"); hud(d, 2, 4)
    d.sprite(72, 1, 2).digits(80, 1, ("m", 3), 3)
    d.branch(9, "eq", 0, "no_shield_hud").rect(52, 2, 14, 2, 8).label("no_shield_hud")
    d.branch(7, "eq", 0, "done").rect(49, 2, 18, 3, 2).label("done").op("halt")
    # Predictive flight controller, with the same physics and hazards as a person.
    auto = A().put(28, 14).put(29, 1800).put(25, 0).label("look")
    auto.put(24, 6).op("mul", 24, 25, 24).put(23, 64).op("add", 24, 24, 23).field(0, 0)
    auto.branchreg(0, "lt", -100, "look_next").op("lt", 1, 0, 29).op("jz", 1, "look_next").put(29, ("r", 0)).field(1, 1).field(2, 2)
    auto.branchreg(2, "eq", 0, "vertical_aim").branchreg(1, "lt", 18, "aim_low").put(28, 9).op("jump", "look_next")
    auto.label("vertical_aim").branchreg(1, "lt", 12, "aim_low").put(28, 9).op("jump", "look_next")
    auto.label("aim_low").put(28, 21)
    auto.label("look_next").put(0, 1).op("add", 25, 25, 0).branchreg(25, "lt", 3, "look")
    auto.put(0, ("m", 1)).put(1, 5).op("mul", 0, 0, 1).put(1, ("m", 0)).op("add", 0, 0, 1)
    auto.put(1, 100).op("mul", 1, 28, 1).op("lt", 2, 1, 0).put(0, 0).op("jz", 2, "done").put(0, 16).label("done").op("halt")
    palette = ["#000000", "#75e8f0", "#ff4f7b", "#ffda69", "#050d18", "#e8f5ff", "#111f33", "#ff8b37", "#5af4ef", "#b179ed", "#334965", "#ff3b30", "#1b314a"]
    sprites = [
        ["00555000","05515500","05111500","aa111500","aa115500","07111100","00100100","00100100"],
        ["07000000","73700000","37370000","73700000","07000000","00000000","00000000","00000000"],
        ["03000000","35300000","03000000","00000000","00000000","00000000","00000000","00000000"],
        ["08800000","85580000","85580000","08800000","00000000","00000000","00000000","00000000"],
        ["00000000","0222a777","25555577","0222a777","00000000","00000000","00000000","00000000"],
        ["25200000","25200000","00000000","00000000","00000000","00000000","00000000","00000000"],
        ["00200000","02200000","22200000","02200000","00200000","00000000","00000000","00000000"],
    ]
    return {"abi":1,"palette":palette,"sprites":sprites,"memory":memory,"init":init.code,"step":s.code,"draw":d.code,"auto":auto.code}


def main():
    from PIL import Image, ImageDraw
    root = Path(__file__).resolve().parents[2]; folder = root / "Games/Jetpack Run"; (folder / "data").mkdir(parents=True,exist_ok=True)
    manifest = {"format":2,"id":"jetpack-run","name":"Jetpack Run","version":"1.0.0","by":"mooboard",
                "description":"Fly through a neon lab, collect coins, and dodge lasers and incoming missiles.",
                "category":"Games","uses":"game","minFirmware":"0.4.1","settings":[{"key":"speed","type":"choice","label":"Game speed","default":"Normal","options":["Slow","Normal","Fast"]}]}
    (folder / "mooboard.json").write_text(json.dumps(manifest,indent=2)+'\n')
    (folder / "data/game.json").write_text(json.dumps(source(),indent=2)+'\n')
    (folder / "README.md").write_text('# Jetpack Run\n\nAn original Joyride-style runner for mooboard. Hold A or Up to rise; release to fall. Collect coins and shield orbs. Dodge vertical zappers, horizontal lasers, and missiles with a flashing entry warning. The lab scrolls in layers, the jetpack flames animate, and speed increases with score. Three lives; A/B restarts. Automatic play uses the same rules.\n\nAll logic, original sprites, and automatic controls are game ABI 1 package data. No new native firmware renderer. Requires the universal runtime targeting firmware 0.4.1.\n')
    image=Image.new('RGB',(32,32),'#08111c'); draw=ImageDraw.Draw(image)
    draw.rectangle((11,8,20,23),fill='#75e8f0');draw.rectangle((13,5,20,11),fill='#e8f5ff');draw.rectangle((6,12,10,21),fill='#334965')
    draw.polygon(((6,20),(3,29),(12,24)),fill='#ff8b37');draw.line((25,4,25,23),fill='#ff4f7b',width=3)
    for x,y in ((4,6),(26,27)):draw.ellipse((x,y,x+3,y+3),fill='#ffda69')
    image.save(folder/'icon.png')


if __name__ == '__main__': main()
