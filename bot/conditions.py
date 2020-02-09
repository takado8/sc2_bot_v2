from sc2.ids.unit_typeid import UnitTypeId as unit
from sc2.ids.upgrade_id import UpgradeId as upgrade


class ConditionAttack:
    def __init__(self, ai):
        self.ai = ai

    def none(self):
        pass

    def rush(self):
        return (not self.ai.first_attack) and upgrade.WARPGATERESEARCH in self.ai.state.upgrades

    def defend(self):
        return (not self.ai.first_attack) and self.ai.time > 420

    def dt(self):
        return (not self.ai.first_attack) and self.ai.structures(unit.DARKSHRINE).ready.amount > 0

    def rush_voidray(self):
        return (not self.ai.first_attack) and self.ai.army(unit.VOIDRAY).amount > 1

    def colossus(self):
        return (not self.ai.first_attack) and self.ai.army(unit.COLOSSUS).amount > 1

    def archons(self):
        return (not self.ai.first_attack) and self.ai.army(unit.ARCHON).amount > 2

    def counter_attack(self):
        en = self.ai.enemy_units()
        return en.exists and en.closer_than(40,self.ai.defend_position).amount > 5


class ConditionRetreat:
    def __init__(self,ai):
        self.ai = ai

    def none(self):
        pass

    def adept_proxy(self):
        return self.ai.attack and self.ai.army.amount < (3 if self.ai.time < 300 else 5)

    def stalker_proxy(self):
        return self.ai.attack and self.ai.army.amount < (2 if self.ai.time < 300 else 5)

    def macro(self):
        return self.ai.attack and self.ai.army.amount < 21


class ConditionTransform:
    def __init__(self,ai):
        self.ai = ai

    def none(self):
        pass

    async def adept_defend(self):
        if ((not self.ai.first_attack) and self.ai.time > 340) or (self.ai.after_first_attack and self.ai.army.amount > 4):
            await self.ai.set_strategy('adept_proxy')

    async def stalker_defend(self):
        if ((not self.ai.first_attack) and self.ai.time > 300) or (self.ai.after_first_attack and self.ai.army.amount > 4):
            await self.ai.set_strategy('stalker_proxy')

    async def stalker_proxy(self):
        if self.ai.after_first_attack and self.ai.army.amount > 7:
            await self.ai.set_strategy('2b_colossus')

    async def adept_proxy(self):
        if self.ai.after_first_attack and self.ai.army.amount > 7:
            await self.ai.set_strategy('2b_archons')

    async def two_base_colossus(self):
        if self.ai.after_first_attack and self.ai.army.amount > 13:
            await self.ai.set_strategy('macro')

    async def two_base_archons(self):
        if self.ai.after_first_attack and self.ai.army.amount > 13:
            await self.ai.set_strategy('bio')

    async def macro(self):
        if self.ai.after_first_attack and self.ai.army.amount > 27 and self.ai.time > 1000 and self.ai.minerals > 1000\
                and self.ai.vespene > 500:
            await self.ai.set_strategy('bio')