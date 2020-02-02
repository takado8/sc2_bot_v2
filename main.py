import random
from typing import Optional
from sc2 import run_game, maps, Race, Difficulty, Result, AIBuild
import sc2
from sc2.ids.ability_id import AbilityId as ability
from sc2.ids.unit_typeid import UnitTypeId as unit
from sc2.player import Bot, Computer
from sc2.ids.buff_id import BuffId as buff
from sc2.ids.upgrade_id import UpgradeId as upgrade
from sc2.position import Point2, Point3
from bot.coords import coords as cd
from sc2.unit import Unit
from typing import Union
from bot.enemy_info import EnemyInfo
from strategy.manager import Strategy
from strategy.carrier_madness import CarrierMadness
from strategy.macro import Macro
from strategy.stalker_proxy import StalkerProxy
from strategy.call_of_void import CallOfTheVoid
from strategy.two_base_colossus import TwoBaseColossus
from strategy.two_base_archons import TwoBaseArchons
from strategy.bio import Bio
from strategy.adept_proxy import AdeptProxy
from strategy.adept_defend import AdeptDefend
from strategy.stalker_defend import StalkerDefend
from strategy.dt import Dt
from bot.plot import plot


class Octopus(sc2.BotAI):
    enemy_attack = False
    second_ramp = None
    enemy_main_base_down = False
    first_attack = False
    attack = False
    after_first_attack = False
    bases_ids = [unit.NEXUS, unit.COMMANDCENTER, unit.COMMANDCENTERFLYING, unit.ORBITALCOMMAND, unit.ORBITALCOMMANDFLYING,
                 unit.PLANETARYFORTRESS, unit.HIVE, unit.HATCHERY, unit.LAIR]
    army_ids = [unit.ADEPT, unit.STALKER, unit.ZEALOT, unit.SENTRY, unit.OBSERVER, unit.IMMORTAL, unit.ARCHON,
                 unit.HIGHTEMPLAR, unit.DARKTEMPLAR, unit.WARPPRISM, unit.VOIDRAY, unit.CARRIER, unit.COLOSSUS, unit.TEMPEST]
    units_to_ignore = [unit.LARVA, unit.EGG, unit.INTERCEPTOR]
    workers_ids = [unit.SCV, unit.PROBE, unit.DRONE]
    proper_nexus_count = 1
    army = []
    known_enemies = []
    game_map = None
    leader_tag = None
    defend_position = None
    destination = None
    prev_nexus_count = 0
    coords = None
    change_position = False

    strategy: Strategy = None
    starting_strategy = None

    units_tags = []
    enemy_tags = []
    proxy_worker = None
    observer_scouting_index = 0
    observer_scounting_points = []
    psi_storm_wait = 0
    nova_wait = 0
    # observer_released = False
    slow = True

    # linear function coefficients for bulid spot validation
    coe_a1 = None
    coe_a2 = None
    coe_b1 = None
    coe_b2 = None
    n = None
    g1 = None
    g2 = None
    r = None
    linear_func = None

    # gate_defender
    defend_rush = False
    gate_defender_tag = None
    gate_locked = False
    enemy_info = None

    times = []
    y1 = []
    y2 = []


    async def on_start(self):
        # enemy_info
        self.enemy_info = EnemyInfo(self)
        strategy_name = await self.enemy_info.pre_analysis()
        if not strategy_name:
            strategy_name = 'stalker_proxy'
            await self.chat_send('UNKNOWN STRATEGY: ' + strategy_name + '  ||  setting default.')
        self.starting_strategy = strategy_name
        await self.set_strategy(strategy_name)

        map_name = str(self.game_info.map_name)
        print('map_name: ' + map_name)
        # print('start location: ' + str(self.start_location.position))
        self.coords = cd[map_name][self.start_location.position]
        self.compute_coeficients_for_buliding_validation()

    async def on_end(self, game_result: Result):
        if game_result == Result.Victory:
            score = 1
        else:
            score = 0
        plot(self.times,self.y1,self.y2)

        self.enemy_info.post_analysis(score)
        self.print_stats()

    async def on_step(self, iteration):
        self.numbers()
        self.set_game_step()
        self.assign_defend_position()
        self.army = self.units().filter(lambda x: x.type_id in self.army_ids)
        await self.morph_Archons()
        self.train_workers()
        await self.distribute_workers()
        await self.morph_gates()
        await self.pylon_first_build()
        await self.pylon_next_build()
        await self.expand()
        await self.proxy()
        await self.transformation()
        # await self.cannons_build()
        # await self.gate_guard()
        if self.structures(unit.NEXUS).amount >= self.proper_nexus_count or self.already_pending(unit.NEXUS) or self.minerals > 400:
            await self.templar_archives_upgrades()
            await self.fleet_beacon_upgrades()
            self.cybernetics_core_upgrades()
            await self.twilight_upgrades()
            self.forge_upgrades()
            await self.twilight_council_build()
            await self.dark_shrine_build()
            await self.templar_archives_build()
            await self.robotics_build()
            await self.robotics_bay_build()
            await self.stargate_build()
            await self.forge_build()
            await self.cybernetics_core_build()
            await self.gate_build()
            self.build_assimilators()
            self.robotics_train()
            self.strategy.stargate_train()
            self.gate_train()
            await self.strategy.warpgate_train()
        await self.nexus_buff()

        # counter attack
        if self.counter_attack_condition() or self.attack_condition():
            self.first_attack = True
            self.attack = True

        # retreat
        if self.retreat_condition():
            self.attack = False
            self.after_first_attack = True

        await self.micro_units()

        if self.attack:
            await self.attack_formation()
        else:
            await self.defend()

        await self.warp_prism()

    # =============================================

    async def set_strategy(self, strategy_name):
        await self.chat_send('Setting strategy: '+ strategy_name)
        if strategy_name == 'adept_defend':
            self.strategy = AdeptDefend(self)
        elif strategy_name == 'dt':
            self.strategy = Dt(self)
        elif strategy_name == 'adept_proxy':
            self.strategy = AdeptProxy(self)
        elif strategy_name == 'stalker_proxy':
            self.strategy = StalkerProxy(self)
        elif strategy_name == 'stalker_defend':
            self.strategy = StalkerDefend(self)
        elif strategy_name == 'bio':
            self.strategy = Bio(self)
        elif strategy_name == 'void':
            self.strategy = CallOfTheVoid(self)
        elif strategy_name == 'air':
            self.strategy = CarrierMadness(self)
        elif strategy_name == '2b_colossus':
            self.strategy = TwoBaseColossus(self)
        elif strategy_name == '2b_archons':
            self.strategy = TwoBaseArchons(self)
        elif strategy_name == 'macro':
            self.strategy = Macro(self)
        else:
            self.strategy = StalkerProxy(self)

    def numbers(self):
        lost_cost = self.state.score.lost_minerals_army + self.state.score.lost_vespene_army
        killed_cost = self.state.score.killed_minerals_army + self.state.score.killed_vespene_army
        if lost_cost != 0 or killed_cost != 0:
            self.times.append(self.time)
            self.y1.append(lost_cost)
            self.y2.append(killed_cost)

        # print('lost_cost: ' + str(lost_cost))
        # print('killed_cost: ' + str(killed_cost))

        # total_value_units = self.state.score.total_value_units
        # total_value_enemy = self.state.score.killed_value_units
        # dmg_taken_shields = self.state.score.total_damage_taken_shields
        # dmg_dealt_shields = self.state.score.total_damage_dealt_shields
        # dmg_taken_life = self.state.score.total_damage_taken_life
        # dmg_dealt_life = self.state.score.total_damage_dealt_life
        # print('total_value_units: ' + str(total_value_units))
        # print('total_value_enemy: ' + str(total_value_enemy))
        # print('dmg_taken_shields: ' + str(dmg_taken_shields))
        # print('dmg_dealt_shields: ' + str(dmg_dealt_shields))
        # print('dmg_taken_life: ' + str(dmg_taken_life))
        # print('dmg_dealt_life: ' + str(dmg_dealt_life))


    async def gate_guard(self):
        if 300 > self.time > 115:
            if not self.gate_locked:
                self.defend_rush = True
            defender = self.units().find_by_tag(self.gate_defender_tag)
            # assign defender
            if self.gate_defender_tag is None or defender is None:
                self.gate_defender_tag = self.units(unit.PROBE).prefer_idle.random.tag
            # defender on position
            elif defender.distance_to(self.main_base_ramp.protoss_wall_warpin) > 4:
                self.do(defender.move(self.main_base_ramp.protoss_wall_warpin.towards(self.main_base_ramp.top_center,-3)))
                self.do(defender.hold_position(queue=True))
            # build pylon wall
            enemy = self.enemy_units()
            if defender and enemy.exists:
                enemy = enemy.closer_than(7, self.main_base_ramp.bottom_center)
                if enemy.amount > 1:
                    print('building pylon!')
                    print('minerals:' + str(self.minerals))
                    done = await self.build(unit.PYLON, near=Point2(self.coords['pylon_block']), placement_step=0,
                        max_distance=0, build_worker=defender, random_alternative=False, block=True)
                    if done:
                        self.gate_locked = True
                        self.defend_rush = False
            # if self.gate_locked:   # cancel
            #     if enemy.amount < 1 or enemy.closer_than(9, self.main_base_ramp.top_center).amount < 1:
            #         pylon = self.structures().filter(lambda x: x.distance_to(Point2(self.coords['pylon_block'])) < 2 and
            #                                          not x.is_ready)
            #         if pylon.exists:
            #             pylon = pylon.random


    # ============================================= Builders
    async def gate_build(self):
        await self.strategy.gate_build()

    async def stargate_build(self):
        await self.strategy.stargate_build()

    async def forge_build(self):
        await self.strategy.forge_build()

    async def robotics_build(self):
        await self.strategy.robotics_build()

    async def robotics_bay_build(self):
        await self.strategy.robotics_bay_build()

    async def twilight_council_build(self):
        await self.strategy.twilight_build()

    async def templar_archives_build(self):
        await self.strategy.templar_archives_build()

    async def dark_shrine_build(self):
        await self.strategy.dark_shrine_build()

    async def pylon_first_build(self):
        await self.strategy.pylon_first_build()

    async def pylon_next_build(self):
        await self.strategy.pylon_next_build()

    async def proxy(self):
        await self.strategy.proxy()

    async def cybernetics_core_build(self):
        await self.strategy.cybernetics_build()

    def build_assimilators(self):
        self.strategy.assimilator_build()

    async def cannons_build(self):
        await self.strategy.cannons_build()

    async def expand(self):
        await self.strategy.expand()

    # ============================================= Upgraders
    def cybernetics_core_upgrades(self):
        self.strategy.cybernetics_upgrades()

    def forge_upgrades(self):
        self.strategy.forge_upgrades()

    async def twilight_upgrades(self):
        await self.strategy.twilight_upgrades()

    async def templar_archives_upgrades(self):
        await self.strategy.templar_archives_upgrades()

    async def fleet_beacon_upgrades(self):
        await self.strategy.fleet_beacon_upgrades()

    # ============================================= Trainers
    def train_workers(self):
        self.strategy.nexus_train()

    def gate_train(self):
        self.strategy.gate_train()

    def robotics_train(self):
        self.strategy.robotics_train()

    async def warpgate_train(self):
        await self.strategy.warpgate_train()

    # ============================================= Army

    async def micro_units(self):
        await self.strategy.micro()

    async def attack_formation(self):
        await self.strategy.movements()

    # ======================================================= Conditions

    def attack_condition(self):
        return self.strategy.attack_condition()

    def counter_attack_condition(self):
        return self.strategy.counter_attack_condition()

    def retreat_condition(self):
        return self.strategy.retreat_condition()

    async def transformation(self):
        await self.strategy.transformation()

    # ============================================= none

    # async def on_unit_destroyed(self, unit_tag):
    #     for ut in self.units_tags:
    #         if ut[0] == unit_tag:
    #             # friendly unit died

    # async def on_unit_created(self, _unit):
    #     self.units_tags.append((_unit.tag, _unit.type_id))

    def set_game_step(self):
        if self.enemy_units().exists:
            self._client.game_step = 4
        else:
            self._client.game_step = 8

    def scan(self):
        phxs = self.units(unit.PHOENIX).filter(lambda z: z.is_hallucination)
        if phxs.amount < 2:
            snts = self.army(unit.SENTRY).filter(lambda z: z.energy >= 75)
            if snts:
                for se in snts:
                    self.do(se(ability.HALLUCINATION_PHOENIX))
                phxs = self.units(unit.PHOENIX).filter(lambda z: z.is_hallucination)
        if phxs:
            if len(self.observer_scounting_points) == 0:
                for exp in self.expansion_locations:
                    if not self.structures().closer_than(12,exp).exists:
                        self.observer_scounting_points.append(exp)
                self.observer_scounting_points = sorted(self.observer_scounting_points,
                                                        key=lambda x: self.enemy_start_locations[0].distance_to(x))
            for px in phxs.idle:
                self.do(px.move(self.observer_scounting_points[self.observer_scouting_index]))
                self.observer_scouting_index += 1
                if self.observer_scouting_index == len(self.observer_scounting_points):
                    self.observer_scouting_index = 0

    async def morph_Archons(self):
        if upgrade.PSISTORMTECH is self.state.upgrades or self.already_pending_upgrade(upgrade.PSISTORMTECH):
            archons = self.army(unit.ARCHON)
            ht_amount = int(archons.amount / 2)
            ht_thresh = ht_amount + 1
        else:
            ht_thresh = 1
        if self.units(unit.HIGHTEMPLAR).amount > ht_thresh:
            hts = self.units(unit.HIGHTEMPLAR).sorted(lambda u: u.energy)
            ht2 = hts[0]
            ht1 = hts[1]
            if ht2 and ht1:
                for ht in self.army(unit.HIGHTEMPLAR):
                    if ht.tag == ht1.tag or ht.tag==ht2.tag:
                        self.army.remove(ht)
                if ht1.distance_to(ht2) > 4:
                    if ht1.distance_to(self.main_base_ramp.bottom_center) > 30:
                        self.do(ht1.move(ht2))
                        self.do(ht2.move(ht1))
                    else:
                        self.do(ht1.move(self.main_base_ramp.bottom_center))
                        self.do(ht2.move(self.main_base_ramp.bottom_center))
                else:
                    # print('morphing!')
                    from s2clientprotocol import raw_pb2 as raw_pb
                    from s2clientprotocol import sc2api_pb2 as sc_pb
                    command = raw_pb.ActionRawUnitCommand(
                        ability_id=ability.MORPH_ARCHON.value,
                        unit_tags=[ht1.tag,ht2.tag],
                        queue_command=False
                    )
                    action = raw_pb.ActionRaw(unit_command=command)
                    await self._client._execute(action=sc_pb.RequestAction(
                        actions=[sc_pb.Action(action_raw=action)]
                    ))

    async def build_batteries(self):
        if self.structures(unit.CYBERNETICSCORE).ready.exists and self.minerals > 360:
            nexuses = self.structures(unit.NEXUS).further_than(9, self.start_location)
            amount = nexuses.amount * 2
            for nex in nexuses:
                pos = nex.position.towards(self.game_info.map_center, 7)
                pylon = self.structures(unit.PYLON).closer_than(7, pos)
                if not pylon.exists and not self.already_pending(unit.PYLON) and self.can_afford(unit.PYLON):
                    await self.build(unit.PYLON, near=pos)
                elif pylon.ready.exists:
                    batteries = self.structures(unit.SHIELDBATTERY)
                    if not batteries.exists or batteries.closer_than(9, pos).amount < amount:
                        if self.can_afford(unit.SHIELDBATTERY) and self.already_pending(unit.SHIELDBATTERY) < 2:
                            await self.build(unit.SHIELDBATTERY, near=pos)

    def forge_upg_priority(self):
        if self.structures(unit.TWILIGHTCOUNCIL).ready.exists:
            upgds = [upgrade.PROTOSSGROUNDWEAPONSLEVEL1,upgrade.PROTOSSGROUNDARMORSLEVEL2,upgrade.PROTOSSSHIELDSLEVEL1]
        else:
            upgds = [upgrade.PROTOSSGROUNDWEAPONSLEVEL1,upgrade.PROTOSSGROUNDARMORSLEVEL1,upgrade.PROTOSSSHIELDSLEVEL1]
        done = True
        for u in upgds:
            if u not in self.state.upgrades:
                done = False
                break
        if not done:
            if self.structures(unit.FORGE).ready.idle.exists:
                return True
        return False

    async def warp_prism(self):
        if self.attack:
            dist = self.enemy_start_locations[0].distance_to(self.game_info.map_center) * 0.8
            for warp in self.units(unit.WARPPRISM):
                if warp.distance_to(self.enemy_start_locations[0]) <= dist:
                    abilities = await self.get_available_abilities(warp)
                    if ability.MORPH_WARPPRISMPHASINGMODE in abilities:
                        self.do(warp(ability.MORPH_WARPPRISMPHASINGMODE))
        else:
            for warp in self.units(unit.WARPPRISMPHASING):
                abilities = await self.get_available_abilities(warp)
                if ability.MORPH_WARPPRISMTRANSPORTMODE in abilities:
                    self.do(warp(ability.MORPH_WARPPRISMTRANSPORTMODE))

    async def defend(self):
        enemy = self.enemy_units()
        if 3 > enemy.amount > 0:
            for st in self.army({unit.STALKER, unit.OBSERVER, unit.ADEPT, unit.VOIDRAY}):
                self.do(st.attack(enemy.closest_to(st)))
            zlts = self.army(unit.ZEALOT)
            if zlts:
                for zl in zlts.further_than(13, self.defend_position):
                    self.do(zl.move(Point2(self.defend_position)))
        elif enemy.amount > 2:
            dist = 12
            for man in self.army:
                position = Point2(self.defend_position).towards(self.game_info.map_center,3) if \
                    man.type_id == unit.ZEALOT else Point2(self.defend_position)
                if man.distance_to(self.defend_position) > dist:
                    self.do(man.attack(position.random_on_distance(random.randint(1,2))))
        else:
            dist = 7
            for man in self.army:
                position = Point2(self.defend_position).towards(self.game_info.map_center,3) if \
                    man.type_id == unit.ZEALOT else Point2(self.defend_position)
                if man.distance_to(self.defend_position) > dist:
                    self.do(man.move(position.random_on_distance(random.randint(1,2))))

    def assign_defend_position(self):
        nex = self.structures(unit.NEXUS)
        enemy = self.enemy_units()

        # start = self.start_location.position
        # self.defend_position = self.coords['defend_pos']

        # if self.prev_nexus_count != nex.amount or enemy.exists or self.change_position:
        # if self.change_position:
        #     self.change_position = False
        # else:
        #     self.change_position = True
        # self.prev_nexus_count = nex.amount
        if enemy.exists and enemy.closer_than(50,self.start_location).amount > 1:
            self.defend_position = enemy.closest_to(self.enemy_start_locations[0]).position
        elif nex.amount < 2:
            self.defend_position = self.main_base_ramp.top_center.towards(self.main_base_ramp.bottom_center, -6)
        elif nex.amount == 2:
            self.defend_position = self.coords['defend_pos']
        else:
            self.defend_position = nex.closest_to(self.enemy_start_locations[0]).position.towards(self.game_info.map_center,5)

            # c = 0
            # total_dists = []
            # for nx1 in nex:
            #     for nx2 in nex:
            #         c += nx1.distance_to(nx2)
            #     total_dists.append(c)
            #     c = 0
            # i = 0
            # idx = 0
            # _min = 999
            # for d in total_dists:
            #     if d < _min:
            #         _min = d
            #         idx = i
            #     i += 1
            # self.defend_position = nex[idx].position.towards(self.game_info.map_center,5)


    def get_proper_pylon(self):
        properPylons = self.structures().filter(lambda unit_: unit_.type_id == unit.PYLON and unit_.is_ready and
            unit_.distance_to(self.start_location.position) < 27)
        if properPylons.exists:
            min_neighbours = 99
            pylon = None
            for pyl in properPylons:
                neighbours = self.structures().filter(lambda unit_: unit_.distance_to(pyl) < 6).amount
                if neighbours < min_neighbours:
                    min_neighbours = neighbours
                    pylon = pyl
            return pylon
        else:
            print('cant find proper pylon')
            return None

    async def morph_gates(self):
        for gateway in self.structures(unit.GATEWAY).ready:
            abilities = await self.get_available_abilities(gateway)
            if ability.MORPH_WARPGATE in abilities and self.can_afford(ability.MORPH_WARPGATE):
                self.do(gateway(ability.MORPH_WARPGATE))

    async def nexus_buff(self):
        if not self.structures(unit.NEXUS).exists:
            return
        for nexus in self.structures(unit.NEXUS).ready:
            abilities = await self.get_available_abilities(nexus)
            if ability.EFFECT_CHRONOBOOSTENERGYCOST in abilities:
                target = self.structures().filter(lambda x: x.type_id == unit.NEXUS
                                                            and x.is_ready and not x.is_idle and not x.has_buff(
                    buff.CHRONOBOOSTENERGYCOST))
                if target.exists:
                    target = target.random
                else:
                    target = self.structures().filter(lambda x: x.type_id == unit.STARGATE
                                                                and x.is_ready and not x.is_idle and not x.has_buff(
                        buff.CHRONOBOOSTENERGYCOST))
                    if target.exists:
                        target = target.random
                    else:
                        target = self.structures().filter(lambda x: x.type_id == unit.CYBERNETICSCORE
                                                                    and x.is_ready and not x.is_idle and not x.has_buff(
                            buff.CHRONOBOOSTENERGYCOST))
                        if target.exists:
                            target = target.random
                        else:
                            target = self.structures().filter(lambda x: x.type_id == unit.FORGE and x.is_ready
                                                                        and not x.is_idle and not x.has_buff(
                                buff.CHRONOBOOSTENERGYCOST))
                            if target.exists:
                                target = target.random
                            else:
                                target = self.structures().filter(
                                    lambda x: (x.type_id == unit.ROBOTICSFACILITY)
                                              and x.is_ready and not x.is_idle and not x.has_buff(
                                        buff.CHRONOBOOSTENERGYCOST))
                                if target.exists:
                                    target = target.random

                                # else:
                                #     target = self.structures().filter(lambda x: (x.type_id == unit.GATEWAY or x.type_id == unit.WARPGATE)
                                #                                            and x.is_ready and not x.is_idle and not x.has_buff(
                                #         buff.CHRONOBOOSTENERGYCOST))
                                #     if target.exists:
                                #         target = target.random
                if target:
                    self.do(nexus(ability.EFFECT_CHRONOBOOSTENERGYCOST,target))

    async def nexus_buff2(self):
        if not self.structures(unit.NEXUS).exists:
            return
        for nexus in self.structures(unit.NEXUS).ready:
            abilities = await self.get_available_abilities(nexus)
            if ability.EFFECT_CHRONOBOOSTENERGYCOST in abilities:
                target = self.structures().filter(lambda x: x.type_id == unit.NEXUS
                               and x.is_ready and not x.is_idle and not x.has_buff(buff.CHRONOBOOSTENERGYCOST))
                if target.exists:
                    target = target.random
                else:
                    target = self.structures().filter(lambda x: x.type_id == unit.STARGATE
                        and x.is_ready and not x.is_idle and not x.has_buff(buff.CHRONOBOOSTENERGYCOST))
                    if target.exists:
                        target = target.random
                    else:
                        # target = self.structures().filter(lambda x: x.type_id == unit.CYBERNETICSCORE
                        #                 and x.is_ready and not x.is_idle and not x.has_buff(buff.CHRONOBOOSTENERGYCOST))
                        # if target.exists:
                        #     target = target.random
                        # else:
                        target = self.structures().filter(
                            lambda x: (x.type_id == unit.ROBOTICSFACILITY)
                                      and x.is_ready and not x.is_idle and not x.has_buff(
                                buff.CHRONOBOOSTENERGYCOST))
                        if target.exists:
                            target = target.random

                        else:
                            target = self.structures().filter(lambda x: x.type_id == unit.FORGE and x.is_ready
                                                                        and not x.is_idle and not x.has_buff(
                                buff.CHRONOBOOSTENERGYCOST))
                            if target.exists:
                                target = target.random
                            else:
                                target = self.structures().filter(lambda x: (x.type_id == unit.GATEWAY or
                                                x.type_id == unit.WARPGATE) and x.is_ready
                                                and not x.is_idle and not x.has_buff(buff.CHRONOBOOSTENERGYCOST))
                                if target.exists:
                                    target = target.random
                                # else:
                                #     target = self.structures().filter(lambda x: (x.type_id == unit.GATEWAY or x.type_id == unit.WARPGATE)
                                #                                            and x.is_ready and not x.is_idle and not x.has_buff(
                                #         buff.CHRONOBOOSTENERGYCOST))
                                #     if target.exists:
                                #         target = target.random
                if target:
                    self.do(nexus(ability.EFFECT_CHRONOBOOSTENERGYCOST, target))

    async def adept_hunt(self):
        adepts = self.army(unit.ADEPT).ready
        if adepts.amount > 1:
            enemy = self.enemy_units()
            targets = enemy.filter(lambda x: x.type_id in self.workers_ids)
            if targets:
                destination = targets.closest_to(self.defend_position)
            else:
                destination = self.enemy_start_locations[0]

            for adept in adepts:
                if enemy.exists:
                    threats = enemy.filter(lambda x: x.can_attack_ground and x.distance_to(adept) < x.ground_range + 1)
                    if threats.exists:
                        # shadow
                        if ability.ADEPTPHASESHIFT_ADEPTPHASESHIFT in await self.get_available_abilities(adept):
                            self.do(adept(ability.ADEPTPHASESHIFT_ADEPTPHASESHIFT,destination))
                        # closest_enemy = threats.closest_to(adept)
                        # # micro
                        # i = 3
                        # pos = adept.position.towards(closest_enemy.position,-i)
                        # while not self.in_pathing_grid(pos) and i < 12:
                        #     # print('func i: ' + str(i))
                        #     pos = adept.position.towards(closest_enemy.position,-i)
                        #     i += 1
                        #     j = 1
                        #     while not self.in_pathing_grid(pos) and j < 9:
                        #         # print('func j: ' + str(j))
                        #         pos = pos.random_on_distance(j)
                        #         j += 1
                        # if not pos:
                        pos = self.defend_position
                        self.do(adept.move(pos))
                    elif targets.exists:
                        targets = targets.filter(lambda x: x.distance_to(adept) < 12)
                        if targets.exists:
                            closest = targets.closest_to(adept)
                            target = targets.sorted(lambda x: x.health + x.shield)[0]
                            if self.enemy_race == Race.Protoss:
                                shield = target.shield_percentage
                            else:
                                shield = 1
                            if target.health_percentage * shield == 1 or \
                                    target.distance_to(adept) > closest.distance_to(adept) + 5:
                                target = closest
                            self.do(adept.attack(target))
                else:
                    self.do(adept.attack(destination))
            for shadow in self.units(unit.ADEPTPHASESHIFT):
                self.do(shadow.move(destination))

    async def blink(self, stalker, target):
        abilities = await self.get_available_abilities(stalker)
        if ability.EFFECT_BLINK_STALKER in abilities:
            self.do(stalker(ability.EFFECT_BLINK_STALKER, target))
            return True
        else:
            return False

    def compute_coeficients_for_buliding_validation(self):
        self.n = self.structures(unit.NEXUS).closest_to(self.start_location).position
        vespenes = self.vespene_geyser.closer_than(9,self.n)
        self.g1 = vespenes.pop(0).position
        self.g2 = vespenes.pop(0).position

        delta1 = (self.g1.x - self.n.x)
        if delta1 != 0:
            self.coe_a1 = (self.g1.y - self.n.y) / delta1
            self.coe_b1 = self.n.y - self.coe_a1 * self.n.x
        delta2 = (self.g2.x - self.n.x)
        if delta2 != 0:
            self.coe_a2 = (self.g2.y - self.n.y) / delta2
            self.coe_b2 = self.n.y - self.coe_a2 * self.n.x
        max_ = 0
        minerals = self.mineral_field.closer_than(9,self.n)
        minerals.append(self.g1)
        minerals.append(self.g2)
        for field in minerals:
            d = self.n.distance_to(field)
            if d > max_:
                max_ = d
        self.r = int(max_)
        if self.start_location.position.y < self.enemy_start_locations[0].position.y:
            self.linear_func = self.line_less_than
        else:
            self.linear_func = self.line_bigger_than

    def is_valid_location(self, x, y):
        condition1 = self.in_circle(x,y)
        if not condition1:
            return True  # outside of circle is a valid location for sure
        condition2 = self.linear_func(x,y,self.coe_a1, self.coe_b1)
        if not condition2:
            return True
        condition3 = self.linear_func(x,y,self.coe_a2, self.coe_b2)
        if not condition3:
            return True
        return False

    def in_circle(self, x, y):
        return (x - self.n.x)**2 + (y - self.n.y)**2 < self.r**2

    @staticmethod
    def line_less_than(x, y, a, b):
        return y < a * x + b

    @staticmethod
    def line_bigger_than(x,y,a,b):
        return y > a * x + b

    async def build(self, building: unit, near: Union[Unit, Point2, Point3], max_distance: int = 20, block=False,
        build_worker: Optional[Unit] = None, random_alternative: bool = True, placement_step: int = 3,) -> bool:
        assert isinstance(near, (Unit, Point2, Point3))
        if isinstance(near, Unit):
            near = near.position
        near = near.to2
        if not self.can_afford(building, check_supply_cost=not block):
            # print('cant afford')
            return False

        p = await self.find_placement(building, near, max_distance, random_alternative, placement_step)
        if p is None:
            # print('position none')
            return False
        # validate
        if building == unit.PHOTONCANNON or self.is_valid_location(p.x,p.y):
            # print("valid location: " + str(p))
            builder = build_worker or self.select_build_worker(p)
            if builder is None:
                return False
            self.do(builder.build(building, p), subtract_cost=True)
            return True
        # else:
        #     print("not valid location for " + str(building)+" :  " + str(p))

    def can_afford(self, item_id: Union[unit, upgrade, ability], check_supply_cost: bool = True) -> bool:
        cost = self.calculate_cost(item_id)

        if self.defend_rush and check_supply_cost:
            a = 100
        else:
            a = 0

        if cost.minerals + a > self.minerals or cost.vespene > self.vespene:
            return False
        if check_supply_cost and isinstance(item_id, unit):
            supply_cost = self.calculate_supply_cost(item_id)
            if supply_cost and supply_cost > self.supply_left:
                return False
        return True

    def print_buildings_positions(self):
        for structure in self.structures().exclude_type({unit.NEXUS, unit.ASSIMILATOR}):
            print(str(structure.type_id)+' coords: ' + str(structure.position))

    def print_stats(self, short=True):
        lost_cost = self.state.score.lost_minerals_army + self.state.score.lost_vespene_army
        killed_cost = self.state.score.killed_minerals_army + self.state.score.killed_vespene_army
        print('lost_cost: ' + str(lost_cost))
        print('killed_cost: ' + str(killed_cost))
        if short:
            return
        # print('score: ' + str(self.state.score.score))
        total_value_units = self.state.score.total_value_units
        total_value_enemy = self.state.score.killed_value_units
        dmg_taken_shields = self.state.score.total_damage_taken_shields
        dmg_dealt_shields = self.state.score.total_damage_dealt_shields
        ff = self.state.score.friendly_fire_minerals_army
        dmg_taken_life = self.state.score.total_damage_taken_life
        dmg_dealt_life = self.state.score.total_damage_dealt_life
        print('friendly_fire: ' + str(ff))
        print('total_value_units: ' + str(total_value_units))
        print('total_value_enemy: ' + str(total_value_enemy))
        print('dmg_taken_shields: ' + str(dmg_taken_shields))
        print('dmg_dealt_shields: ' + str(dmg_dealt_shields))
        print('dmg_taken_life: ' + str(dmg_taken_life))
        print('dmg_dealt_life: ' + str(dmg_dealt_life))
        print('start pos: ' + str(self.start_location.position))


def test(real_time):
    r = 1
    if real_time == 1:
        real_time = True
    else:
        real_time = False
    for i in range(r):
        # try:
        botVsComputer(real_time)
        # except Exception as ex:
        #     print('Error.')
        #     print(ex)


def botVsComputer(real_time):
    maps_set = ['blink', "zealots", "AcropolisLE", "DiscoBloodbathLE", "ThunderbirdLE", "TritonLE", "Ephemeron",
                "WintersGateLE", "WorldofSleepersLE"]
    races = [Race.Protoss, Race.Zerg, Race.Terran]

    # computer_builds = [AIBuild.Rush]
    # computer_builds = [AIBuild.Timing]
    # computer_builds = [AIBuild.Air]
    computer_builds = [AIBuild.Power, AIBuild.Macro]
    build = random.choice(computer_builds)
    # map_index = random.randint(0, 6)
    race_index = random.randint(0, 2)
    res = run_game(map_settings=maps.get(maps_set[2]), players=[
        Bot(race=Race.Protoss, ai=Octopus(), name='Octopus'),
        Computer(race=races[1], difficulty=Difficulty.VeryHard, ai_build=build)
    ], realtime=real_time)
    return res, build, races[race_index]
# CheatMoney   VeryHard


if __name__ == '__main__':
    test(real_time=0)
