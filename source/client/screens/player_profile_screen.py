import pygame
from client.screens.base_screen import BaseScreen
from client.data_models import ClientPlayerProfileData
from client.ui_elements import InputBox
from client.button import Button
from typing import TYPE_CHECKING, Optional, Dict, Any, List, Tuple

from common.constants import DEFENDERS

if TYPE_CHECKING:
    from client.game import Game

# Define font sizes for different highlight levels
FONT_LEVEL_5 = None
FONT_LEVEL_4 = None
FONT_LEVEL_3 = None
FONT_LEVEL_2 = None
FONT_LEVEL_1 = None


class PlayerProfileScreen(BaseScreen):
    """
    Displays detailed information about a player and allows transfer actions.
    Can be accessed from TransfersScreen or SquadScreen.
    """

    def __init__(self, game: 'Game'):
        super().__init__(game)

        global FONT_LEVEL_5, FONT_LEVEL_4, FONT_LEVEL_3, FONT_LEVEL_2, FONT_LEVEL_1
        if FONT_LEVEL_5 is None:
            FONT_LEVEL_5 = self.font_large
            FONT_LEVEL_4 = pygame.font.Font(None, self.constants.FONT_SIZE_MEDIUM + 4)
            FONT_LEVEL_3 = self.font_medium
            FONT_LEVEL_2 = self.font_small
            FONT_LEVEL_1 = pygame.font.Font(None, self.constants.FONT_SIZE_SMALL - 2)

        self.player_data: Optional[ClientPlayerProfileData] = None
        self.loading_state: str = "idle"
        self.error_message: Optional[str] = None
        self.success_message: Optional[str] = None
        self.message_timer: float = 0.0

        self.player_id_to_load: Optional[int] = None
        self.came_from_screen: str = "Transfers"

        self.back_button: Optional[Button] = None
        self.action_button: Optional[Button] = None

        self.show_confirmation: bool = False
        self.confirmation_message: str = ""
        self.confirmation_dialog_rect = pygame.Rect(0, 0, 0, 0)  # Placeholder
        self.confirm_yes_button: Optional[Button] = None
        self.confirm_no_button: Optional[Button] = None
        self.confirm_action_callback: Optional[callable] = None

        self.show_asking_price_input: bool = False
        self.asking_price_dialog_rect = pygame.Rect(0, 0, 0, 0)  # Placeholder
        self.asking_price_input_box: Optional[InputBox] = None
        self.asking_price_confirm_button: Optional[Button] = None
        self.asking_price_cancel_button: Optional[Button] = None

        self.padding = 30
        self.panel_margin_x = 60
        self.panel_margin_y = 40
        self.column_spacing = 150
        self.attribute_line_height = 28
        self.section_spacing = 20

    def on_enter(self, data: Optional[Dict] = None):
        super().on_enter(data)
        self.player_data = None
        self.loading_state = "loading"
        self.error_message = None
        self.success_message = None
        self.message_timer = 0.0
        self.show_confirmation = False
        self.show_asking_price_input = False
        self.action_button = None  # Reset action button
        self.back_button = None  # Reset back button

        if data:
            self.player_id_to_load = data.get("player_id")
            self.came_from_screen = data.get("came_from", "Transfers")
        else:
            self.player_id_to_load = None
            self.came_from_screen = "Transfers"

        if not self.player_id_to_load:
            self.loading_state = "error"
            self.error_message = self.game.labels.get_text("ERROR_PLAYER_NOT_FOUND", "Player ID missing.")
            self._create_static_ui()
            return

        print(f"PlayerProfileScreen: Fetching details for player ID {self.player_id_to_load}")
        profile_data = self.game.request_player_profile_details(self.player_id_to_load)

        if profile_data:
            self.player_data = profile_data
            self.loading_state = "loaded"
            print(f"PlayerProfileScreen: Loaded profile for {self.player_data.name}")
        else:
            self.loading_state = "error"
            self.error_message = self.game.labels.get_text("ERROR_PLAYER_NOT_FOUND")
            print(f"PlayerProfileScreen: Failed to load profile for player ID {self.player_id_to_load}")

        self._create_static_ui()

    def _create_static_ui(self):
        main_rect = self._get_panel_rect()
        btn_h = 45

        self.back_button = Button(
            x=main_rect.left + self.padding,
            y=main_rect.bottom - btn_h - self.padding,
            width=150, height=btn_h,
            text=self.game.labels.get_text("BACK"),
            font_size=self.constants.FONT_SIZE_MEDIUM,
            active_color=self.colors['active_button'], inactive_color=self.colors['inactive_button'],
            border_color=self.colors['border'], text_color=self.colors['text_button'],
            on_click=self.go_back
        )

        self.action_button = None  # Reset
        if self.player_data:
            is_own_player = self.player_data.club_id == self.game.active_club_id

            action_btn_text = "Error"
            action_btn_callback = None
            action_button_is_conditionally_active = True  # Default to active, can be set to False for Buy button

            if self.came_from_screen == "Transfers" and not is_own_player:
                action_btn_text = self.game.labels.get_text("BUTTON_BUY_PLAYER")
                original_on_click_for_action_button = self._initiate_buy_player

                current_budget = 0
                if self.game.active_club_id and self.game.user_clubs:
                    active_club_info = next(
                        (club_info for club_info in self.game.user_clubs if
                         club_info.club_id == self.game.active_club_id),
                        None
                    )
                    if active_club_info and hasattr(active_club_info, 'budget'):
                        current_budget = active_club_info.budget

                can_afford = True  # Assume can afford initially
                if self.player_data.asking_price is None or \
                        current_budget < self.player_data.asking_price:
                    can_afford = False

                action_button_is_conditionally_active = can_afford  # Button active state depends on affordability

            elif (self.came_from_screen == "Transfers" and is_own_player) or \
                    (self.came_from_screen == "Squad"):
                if self.player_data.is_on_transfer_list:
                    action_btn_text = self.game.labels.get_text("BUTTON_REMOVE_FROM_LIST")
                    original_on_click_for_action_button = self._initiate_remove_from_list
                else:
                    action_btn_text = self.game.labels.get_text("BUTTON_LIST_FOR_TRANSFER")
                    original_on_click_for_action_button = self._initiate_list_player
                # For list/remove buttons, they are always "active" in terms of clickability,
                # the logic is handled by the confirmation/checks later.
                action_button_is_conditionally_active = True
            else:
                print(
                    f"Warning: Unknown context for PlayerProfileScreen action button. came_from: {self.came_from_screen}, is_own_player: {is_own_player}")
                original_on_click_for_action_button = None

            if original_on_click_for_action_button:
                # --- Wrapper for logging click ---
                def action_button_on_click_wrapper():
                    print(f"PlayerProfileScreen: Action button '{action_btn_text}' clicked via wrapper!")
                    original_on_click_for_action_button()

                # --- End wrapper ---

                # Determine inactive color based on affordability ONLY for the buy button
                final_inactive_color = self.colors['inactive_button']
                if action_btn_text == self.game.labels.get_text(
                        "BUTTON_BUY_PLAYER") and not action_button_is_conditionally_active:
                    final_inactive_color = (150, 50, 50)  # Reddish for unaffordable buy

                self.action_button = Button(
                    x=main_rect.right - 200 - self.padding,
                    y=main_rect.bottom - btn_h - self.padding,
                    width=200, height=btn_h,
                    text=action_btn_text,
                    font_size=self.constants.FONT_SIZE_MEDIUM,
                    active_color=self.colors['active_button'],
                    inactive_color=final_inactive_color,  # Use determined inactive color
                    border_color=self.colors['border'], text_color=self.colors['text_button'],
                    on_click=action_button_on_click_wrapper  # Use the wrapper
                )
                # Explicitly set the button's internal 'active' state
                # This 'active' flag in the Button class can be used by its draw method
                # for visual cues, but the clickability check in handle_event should also respect it.
                self.action_button.active = action_button_is_conditionally_active

    def _create_confirmation_dialog_ui(self, message: str, yes_action: callable):
        self.confirmation_message = message
        self.confirm_action_callback = yes_action

        dialog_w, dialog_h = 450, 180  # Wider for potentially longer messages
        dialog_x = (self.game.screen.get_width() - dialog_w) // 2
        dialog_y = (self.game.screen.get_height() - dialog_h) // 2
        self.confirmation_dialog_rect = pygame.Rect(dialog_x, dialog_y, dialog_w, dialog_h)

        btn_w, btn_h = 100, 40
        btn_y = dialog_y + dialog_h - btn_h - 20
        spacing = 30

        self.confirm_no_button = Button(
            x=dialog_x + (dialog_w // 2) - btn_w - spacing // 2,
            y=btn_y, width=btn_w, height=btn_h,
            text=self.game.labels.get_text("BUTTON_NO", "No"),
            font_size=self.constants.FONT_SIZE_MEDIUM,
            active_color=self.colors['active_button'], inactive_color=self.colors['inactive_button'],
            border_color=self.colors['border'], text_color=self.colors['text_button'],
            on_click=self._cancel_confirmation
        )
        self.confirm_yes_button = Button(
            x=dialog_x + (dialog_w // 2) + spacing // 2,
            y=btn_y, width=btn_w, height=btn_h,
            text=self.game.labels.get_text("BUTTON_YES", "Yes"),
            font_size=self.constants.FONT_SIZE_MEDIUM,
            active_color=self.colors['active_button'], inactive_color=self.colors['inactive_button'],
            border_color=self.colors['border'], text_color=self.colors['text_button'],
            on_click=self._execute_confirm_action
        )
        self.show_confirmation = True

    def _create_asking_price_input_ui(self):
        dialog_w, dialog_h = 400, 220
        dialog_x = (self.game.screen.get_width() - dialog_w) // 2
        dialog_y = (self.game.screen.get_height() - dialog_h) // 2
        self.asking_price_dialog_rect = pygame.Rect(dialog_x, dialog_y, dialog_w, dialog_h)

        input_w, input_h = dialog_w - 60, 40
        input_x = dialog_x + 30
        input_y = dialog_y + 70  # Adjusted Y for prompt

        self.asking_price_input_box = InputBox(
            input_x, input_y, input_w, input_h, self.font_medium,
            placeholder=self.game.labels.get_text("Enter amount...")
        )
        if self.player_data and self.player_data.value:
            self.asking_price_input_box.update_text(str(self.player_data.value))

        btn_w, btn_h = 100, 40
        btn_y = input_y + input_h + 30
        spacing = 30

        self.asking_price_cancel_button = Button(
            x=dialog_x + (dialog_w // 2) - btn_w - spacing // 2,
            y=btn_y, width=btn_w, height=btn_h,
            text=self.game.labels.get_text("CANCEL"),
            font_size=self.constants.FONT_SIZE_MEDIUM,
            active_color=self.colors['active_button'], inactive_color=self.colors['inactive_button'],
            border_color=self.colors['border'], text_color=self.colors['text_button'],
            on_click=self._cancel_asking_price_input
        )
        self.asking_price_confirm_button = Button(
            x=dialog_x + (dialog_w // 2) + spacing // 2,
            y=btn_y, width=btn_w, height=btn_h,
            text=self.game.labels.get_text("CONFIRM"),
            font_size=self.constants.FONT_SIZE_MEDIUM,
            active_color=self.colors['active_button'], inactive_color=self.colors['inactive_button'],
            border_color=self.colors['border'], text_color=self.colors['text_button'],
            on_click=self._confirm_list_with_price
        )
        self.show_asking_price_input = True
        if self.asking_price_input_box:  # Ensure it was created
            self.asking_price_input_box.active = True

    def _initiate_buy_player(self):
        if not self.player_data or self.player_data.asking_price is None: return

        currency_symbol = self.game.labels.get_currency_symbol()
        price_val = self.player_data.asking_price
        price_formatted = f"{price_val:,}"
        if price_val >= 1_000_000:
            price_formatted = f"{price_val / 1_000_000:.1f}M"
        elif price_val >= 1_000:
            price_formatted = f"{price_val / 1_000:.0f}K"

        msg = self.game.labels.get_text("CONFIRM_BUY_PLAYER").format(
            player_name=self.player_data.name,
            currency_symbol=currency_symbol,
            asking_price_formatted=price_formatted
        )
        self._create_confirmation_dialog_ui(msg, self._execute_buy_player)

    def _execute_buy_player(self):
        self.show_confirmation = False
        if not self.player_data or self.player_data.listing_id is None:
            print("Execute buy: Missing player_data or listing_id")
            return

        print(f"Executing buy for player {self.player_data.player_id}")
        self.loading_state = "processing"  # New state for actions
        self._clear_messages_and_redraw()

        success, message, new_budget = self.game.request_buy_player(
            self.player_data.player_id,
            self.player_data.listing_id
        )

        if success:
            self.success_message = self.game.labels.get_text("TRANSFER_ACTION_SUCCESS").format(
                action=self.game.labels.get_text("PLAYER_PURCHASE"))
            # Important: Force reload of player data as their club and transfer status changed
            # Also, the previous screen (Transfers) needs to update.
            self.on_enter({"player_id": self.player_id_to_load, "came_from": self.came_from_screen})
        else:
            self.error_message = self.game.labels.get_text("TRANSFER_ACTION_FAILED").format(
                action=self.game.labels.get_text("PLAYER_PURCHASE"), error=message)
        self.loading_state = "loaded"  # Reset after processing
        self.message_timer = 3.0
        self._create_static_ui()  # Recreate buttons as player's state might have changed action

    def _initiate_list_player(self):
        if not self.player_data: return
        self._create_asking_price_input_ui()

    def _confirm_list_with_price(self):
        if not self.player_data or not self.asking_price_input_box: return

        asking_price_str = self.asking_price_input_box.get_text()
        try:
            asking_price = int(asking_price_str)
            if asking_price <= 0:
                self.error_message = self.game.labels.get_text("INVALID_ASKING_PRICE")
                self.message_timer = 3.0
                return
        except ValueError:
            self.error_message = self.game.labels.get_text("INVALID_ASKING_PRICE")
            self.message_timer = 3.0
            return

        self.show_asking_price_input = False
        msg = self.game.labels.get_text("CONFIRM_LIST_PLAYER").format(player_name=self.player_data.name)
        self._create_confirmation_dialog_ui(msg, lambda: self._execute_list_player(asking_price))

    def _execute_list_player(self, asking_price: int):
        self.show_confirmation = False
        if not self.player_data: return

        print(f"Executing list for player {self.player_data.player_id} at price {asking_price}")
        self.loading_state = "processing"
        self._clear_messages_and_redraw()

        success, message, _ = self.game.request_list_player(self.player_data.player_id, asking_price)

        if success:
            self.success_message = self.game.labels.get_text("TRANSFER_ACTION_SUCCESS").format(
                action=self.game.labels.get_text("PLAYER_LISTING"))
            self.on_enter({"player_id": self.player_id_to_load, "came_from": self.came_from_screen})
        else:
            self.error_message = self.game.labels.get_text("TRANSFER_ACTION_FAILED").format(
                action=self.game.labels.get_text("PLAYER_LISTING"), error=message)
        self.loading_state = "loaded"
        self.message_timer = 3.0
        self._create_static_ui()

    def _initiate_remove_from_list(self):
        if not self.player_data: return
        msg = self.game.labels.get_text("CONFIRM_REMOVE_PLAYER_LISTING").format(player_name=self.player_data.name)
        self._create_confirmation_dialog_ui(msg, self._execute_remove_from_list)

    def _execute_remove_from_list(self):
        self.show_confirmation = False
        if not self.player_data or self.player_data.listing_id is None: return

        print(f"Executing remove from list for player {self.player_data.player_id}")
        self.loading_state = "processing"
        self._clear_messages_and_redraw()

        success, message = self.game.request_remove_from_list(self.player_data.player_id, self.player_data.listing_id)

        if success:
            self.success_message = self.game.labels.get_text("TRANSFER_ACTION_SUCCESS").format(
                action=self.game.labels.get_text("PLAYER_LISTING_REMOVAL"))
            self.on_enter({"player_id": self.player_id_to_load, "came_from": self.came_from_screen})
        else:
            self.error_message = self.game.labels.get_text("TRANSFER_ACTION_FAILED").format(
                action=self.game.labels.get_text("PLAYER_LISTING_REMOVAL"), error=message)
        self.loading_state = "loaded"
        self.message_timer = 3.0
        self._create_static_ui()

    def _clear_messages_and_redraw(self):
        """Clears messages and forces a redraw, useful before server calls."""
        self.error_message = None
        self.success_message = None
        self.message_timer = 0.0
        if pygame.display.get_init():  # Check if display is initialized
            self.draw(self.game.screen)
            pygame.display.flip()

    def _cancel_confirmation(self):
        self.show_confirmation = False
        self.confirm_yes_button = None
        self.confirm_no_button = None
        self.confirm_action_callback = None

    def _execute_confirm_action(self):
        if self.confirm_action_callback:
            self.confirm_action_callback()
        # Resetting show_confirmation is handled by the specific execute_... methods
        # after the action is complete or by _cancel_confirmation.

    def _cancel_asking_price_input(self):
        self.show_asking_price_input = False
        self.asking_price_input_box = None
        self.asking_price_confirm_button = None
        self.asking_price_cancel_button = None
        self.error_message = None  # Clear specific input error
        self.message_timer = 0.0

    def go_back(self):
        self.game.change_screen(self.came_from_screen)

    def handle_event(self, event: pygame.event.Event):
        mouse_pos = pygame.mouse.get_pos()

        if self.show_asking_price_input:
            if self.asking_price_input_box:
                self.asking_price_input_box.handle_event(event)
            if self.asking_price_confirm_button:
                self.asking_price_confirm_button.check_hover(mouse_pos)
            if self.asking_price_cancel_button:
                self.asking_price_cancel_button.check_hover(mouse_pos)

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.asking_price_confirm_button and self.asking_price_confirm_button.check_click(mouse_pos):
                    print("DEBUG: Asking price CONFIRM button clicked")
                    return
                if self.asking_price_cancel_button and self.asking_price_cancel_button.check_click(mouse_pos):
                    print("DEBUG: Asking price CANCEL button clicked")
                    return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: self._cancel_asking_price_input(); return
                if event.key == pygame.K_RETURN:  # Allow Enter if input box is active OR if confirm button is somehow "focused" (not really implemented for buttons)
                    if self.asking_price_input_box and self.asking_price_input_box.active:
                        self._confirm_list_with_price()
                        print("DEBUG: Asking price RETURN (input active)")
                    elif self.asking_price_confirm_button and self.asking_price_confirm_button.hover:  # Pseudo-focus
                        self._confirm_list_with_price()
                        print("DEBUG: Asking price RETURN (confirm hover)")
                    return
            return

        if self.show_confirmation:
            if self.confirm_yes_button: self.confirm_yes_button.check_hover(mouse_pos)
            if self.confirm_no_button: self.confirm_no_button.check_hover(mouse_pos)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.confirm_yes_button and self.confirm_yes_button.check_click(mouse_pos):
                    print("DEBUG: Confirmation YES button clicked")
                    return
                if self.confirm_no_button and self.confirm_no_button.check_click(mouse_pos):
                    print("DEBUG: Confirmation NO button clicked")
                    return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: self._cancel_confirmation(); return
                if event.key == pygame.K_RETURN: self._execute_confirm_action(); return
            return

        if self.back_button: self.back_button.check_hover(mouse_pos)
        if self.action_button: self.action_button.check_hover(mouse_pos)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            print(f"PlayerProfileScreen: MOUSEBUTTONDOWN (no dialog active). Mouse: {mouse_pos}")
            if self.back_button and self.back_button.check_click(mouse_pos):
                print("PlayerProfileScreen: Back button clicked and action triggered.")
                return
            # Ensure action_button exists and is active before checking click
            # --- Detailed Action Button Check ---
            if self.action_button:
                action_btn_active_state = getattr(self.action_button, 'active',
                                                  True)  # Default to True if 'active' not set
                action_btn_rect_collides = self.action_button.rect.collidepoint(mouse_pos)

                print(
                    f"PlayerProfileScreen: ActionButton Check -> Exists: True, Rect: {self.action_button.rect}, Text: '{self.action_button.text}', Active State: {action_btn_active_state}, Collides: {action_btn_rect_collides}")

                if action_btn_rect_collides:  # First check collision
                    if action_btn_active_state is True:  # Then check if active
                        print("PlayerProfileScreen: ActionButton IS ACTIVE and collides. Calling check_click...")
                        if self.action_button.check_click(mouse_pos):
                            print("PlayerProfileScreen: ActionButton.check_click returned True (on_click called).")
                            return
                        else:
                            print(
                                "PlayerProfileScreen: ActionButton.check_click returned False (on_click NOT called or no on_click).")
                    else:  # Button collides but is INACTIVE
                        print("PlayerProfileScreen: ActionButton IS INACTIVE but collides.")
                        # Check if it's the buy button that's inactive due to budget
                        if self.action_button.text == self.game.labels.get_text("BUTTON_BUY_PLAYER"):
                            # Check the reason for inactivity again (should be budget)
                            current_budget = 0
                            if self.game.active_club_id and self.game.user_clubs:
                                active_club_info = next(
                                    (ci for ci in self.game.user_clubs if ci.club_id == self.game.active_club_id), None
                                )
                                if active_club_info: current_budget = active_club_info.budget

                            if self.player_data and self.player_data.asking_price is not None and \
                                    current_budget < self.player_data.asking_price:
                                self.error_message = self.game.labels.get_text("ERROR_INSUFFICIENT_BUDGET")
                                self.success_message = None  # Clear any success message
                                self.message_timer = 3.0  # Show for 3 seconds
                                print(f"PlayerProfileScreen: Displaying insufficient budget message.")
                                return  # Event handled by showing message
            else:
                print("PlayerProfileScreen: self.action_button is None.")
            # --- End Detailed Action Button Check ---

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.go_back()

    def update(self, dt: float):
        if self.message_timer > 0:
            self.message_timer -= dt
            if self.message_timer <= 0:
                self.success_message = None
                self.error_message = None
        if self.show_asking_price_input and self.asking_price_input_box:
            self.asking_price_input_box.update(dt)

    def _get_panel_rect(self) -> pygame.Rect:
        screen_w = self.game.screen.get_width()
        screen_h = self.game.screen.get_height()
        return pygame.Rect(
            self.panel_margin_x, self.panel_margin_y,
            screen_w - 2 * self.panel_margin_x,
            screen_h - 2 * self.panel_margin_y
        )

    def _draw_attribute_group(self, screen: pygame.Surface, attributes: List[Tuple[str, Any, Any]],
                              start_x: int, start_y: int, font_level: pygame.font.Font,
                              label_color: Tuple[int, int, int], value_color: Tuple[int, int, int],
                              is_base_attr_gk_style: bool = False) -> int:
        current_y = start_y
        max_label_width = 0
        if not is_base_attr_gk_style:
            for label_text_key, _, _ in attributes:
                if label_text_key:
                    label_text = self.game.labels.get_text(label_text_key, label_text_key) + ": "
                    w = font_level.size(label_text)[0]
                    if w > max_label_width:
                        max_label_width = w

        value_start_x = start_x + max_label_width + 10  # Increased spacing

        for label_key, value, gk_label_key_override in attributes:
            if value is None or str(value).strip() == "": value = "-"

            final_label_text = ""
            if is_base_attr_gk_style:
                label_text_for_key = self.game.labels.get_text(
                    gk_label_key_override if gk_label_key_override else label_key, label_key)

                label_surf = font_level.render(label_text_for_key, True, label_color)
                label_rect = label_surf.get_rect(centerx=start_x, top=current_y)
                screen.blit(label_surf, label_rect)

                value_surf = FONT_LEVEL_4.render(str(value), True, value_color)
                value_rect = value_surf.get_rect(centerx=start_x, top=label_rect.bottom + 2)
                screen.blit(value_surf, value_rect)

                current_y += self.attribute_line_height * 1.5
            else:
                final_label_text = self.game.labels.get_text(label_key, label_key) + ": "
                self.draw_text(screen, final_label_text, (start_x, current_y + font_level.get_height() // 2),
                               font_level, label_color, center_y=True)
                self.draw_text(screen, str(value), (value_start_x, current_y + font_level.get_height() // 2),
                               font_level, value_color, center_y=True)
                current_y += self.attribute_line_height
        return current_y

    def draw(self, screen: pygame.Surface):
        if self.show_confirmation or self.show_asking_price_input:
            # Draw the main screen dimmed first
            self._draw_main_content(screen, dimmed=True)
            # Then draw the dialog on top
            if self.show_confirmation:
                self._draw_confirmation_dialog(screen)
            elif self.show_asking_price_input:
                self._draw_asking_price_dialog(screen)
        else:
            self._draw_main_content(screen, dimmed=False)

    def _draw_main_content(self, screen: pygame.Surface, dimmed: bool = False):
        """Draws the main profile content, optionally dimmed."""
        if dimmed:
            # Draw current screen content slightly dimmed
            temp_surface = screen.copy()  # Draw on a temporary surface
            bg_image = self.game.assets.get('background')
            if bg_image:
                temp_surface.blit(bg_image, (0, 0))
            else:
                temp_surface.fill(self.colors['background'])
            main_rect_temp = self._get_panel_rect()  # Recalculate for safety
            pygame.draw.rect(temp_surface, self.colors['panel'], main_rect_temp)
            pygame.draw.rect(temp_surface, self.colors['border'], main_rect_temp, 2)
            self._draw_player_attributes(temp_surface, main_rect_temp)  # Draw attributes on temp

            dim_overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            dim_overlay.fill((0, 0, 0, 150))  # Semi-transparent black
            temp_surface.blit(dim_overlay, (0, 0))
            screen.blit(temp_surface, (0, 0))
        else:
            # Normal drawing
            bg_image = self.game.assets.get('background')
            if bg_image:
                screen.blit(bg_image, (0, 0))
            else:
                screen.fill(self.colors['background'])
            main_rect = self._get_panel_rect()
            pygame.draw.rect(screen, self.colors['panel'], main_rect)
            pygame.draw.rect(screen, self.colors['border'], main_rect, 2)
            self._draw_player_attributes(screen, main_rect)

        # Buttons and messages are drawn on top of everything (unless dialogs are open)
        if not self.show_confirmation and not self.show_asking_price_input:
            if self.back_button: self.back_button.draw(screen)
            if self.action_button: self.action_button.draw(screen)

            if self.message_timer > 0:  # Only draw messages if no dialogs
                main_rect_for_msg = self._get_panel_rect()  # Get it again in case screen size changed
                msg_text = self.success_message or self.error_message
                msg_color = self.colors['success_text'] if self.success_message else self.colors['error_text']
                if msg_text:
                    self.draw_text(screen, msg_text, (main_rect_for_msg.centerx, main_rect_for_msg.bottom - 75),
                                   self.font_medium, msg_color, center_x=True)

    def _draw_player_attributes(self, surface_to_draw_on: pygame.Surface, main_rect: pygame.Rect):
        """Helper to draw the player attributes onto a given surface."""
        if self.loading_state == "loading" or self.loading_state == "processing":
            self.draw_text(surface_to_draw_on, self.game.labels.get_text("LOADING"), main_rect.center,
                           self.font_large, self.colors['text_normal'], center_x=True, center_y=True)
            return
        elif self.loading_state == "error" or not self.player_data:
            error_text = self.error_message or self.game.labels.get_text("ERROR_PLAYER_NOT_FOUND")
            self.draw_text(surface_to_draw_on, error_text, main_rect.center,
                           self.font_medium, self.colors['error_text'], center_x=True, center_y=True)
            # Still draw back button if it exists, handled in _draw_main_content
            return

        # If loaded and player_data exists
        p = self.player_data
        current_y = main_rect.top + self.padding


        name_section_height = FONT_LEVEL_5.get_height() + FONT_LEVEL_3.get_height() + 5  # Approximate height for name + nation/club + small spacing
        name_vertical_offset = 25  # Pixels from the top of the content area to the center of the name
        player_name_y = main_rect.top + self.padding + name_vertical_offset

        self.draw_text(surface_to_draw_on, p.name, (main_rect.centerx, player_name_y), FONT_LEVEL_5,
                       self.colors['text_normal'], center_x=True, center_y=True)  # Added center_y=True

        name_text_surface = FONT_LEVEL_5.render(p.name, True, self.colors['text_normal'])
        name_text_rect = name_text_surface.get_rect(center=(main_rect.centerx, player_name_y))

        # Nation and Club Name directly from player object
        nation_text = p.nation or "N/A"  # Use "N/A" if p.nation is None
        club_display_name = p.club_name or self.game.labels.get_text("CLUB_UNATTACHED", "Unattached")  # Use localized "Unattached"
        if p.club_name and p.club_name.startswith(self.constants.FREE_AGENTS_CLUB_NAME_PREFIX):
            club_display_name = self.game.labels.get_text("CLUB_FREE_AGENTS")

        nation_club_text = f"{nation_text}  |  {club_display_name}"
        nation_club_y = player_name_y + FONT_LEVEL_5.get_height() - 5  # Position below name
        self.draw_text(surface_to_draw_on, nation_club_text, (main_rect.centerx, nation_club_y), FONT_LEVEL_3,
                       self.colors['text_normal'], center_x=True)
        # Update current_y for subsequent sections
        nation_club_text_surface = FONT_LEVEL_3.render(nation_club_text, True, self.colors['text_normal'])
        nation_club_text_rect = nation_club_text_surface.get_rect(centerx=main_rect.centerx, top=nation_club_y)
        current_y = nation_club_text_rect.bottom + int(self.section_spacing * 1.2)  # Spacing after nation/club line

        col1_x = main_rect.left + self.padding + 20
        col2_x = main_rect.left + (main_rect.width // 2) + self.column_spacing // 4  # Start of second column

        col1_current_y = current_y

        # Level 4: Age, Position, Overall, Status
        level4_attrs = [
            ("AGE", p.age, None), ("POS", p.position, None),
            ("OVR", p.overall_rating, None), ("STATUS", p.status, None)
        ]
        col1_current_y = self._draw_attribute_group(surface_to_draw_on, level4_attrs, col1_x, col1_current_y,
                                                    FONT_LEVEL_4, self.colors['text_normal'], (220, 220, 100))
        col1_current_y += self.section_spacing

        # Level 3: Preferred Foot, Weak Foot, Skill Moves
        star = "star" if self.game.labels.language == "ENGLISH" else "csillag"
        preferred_foot = self.game.labels.get_text(p.preferred_foot.upper(), "Preferred Foot")
        level3_attrs_col1 = [
            ("ATTR_PREFERRED_FOOT", preferred_foot, None),
            ("ATTR_WEAK_FOOT", f"{p.weak_foot} {star}" if p.weak_foot else "-", None),
            ("ATTR_SKILL_MOVES", f"{p.skill_moves} {star}" if p.skill_moves else "-", None),
        ]
        col1_current_y = self._draw_attribute_group(surface_to_draw_on, level3_attrs_col1, col1_x, col1_current_y,
                                                    FONT_LEVEL_3, self.colors['text_normal'],
                                                    self.colors['text_normal'])
        col1_current_y += self.section_spacing

        # Level 2: Alt Pos, Height, Fitness, Form
        level2_attrs_col1 = [
            ("ATTR_ALT_POSITIONS", p.alternative_positions, None),
            ("ATTR_HEIGHT", f"{p.height_cm} cm" if p.height_cm else "-", None),
            ("ATTR_FITNESS", f"{p.fitness}%", None),
            ("ATTR_FORM", f"{p.form}/100", None),
        ]
        col1_current_y = self._draw_attribute_group(surface_to_draw_on, level2_attrs_col1, col1_x, col1_current_y,
                                                    FONT_LEVEL_2, self.colors['text_normal'],
                                                    self.colors['text_normal'])
        col1_current_y += self.section_spacing

        level1_attrs_col1 = [
            ("ATTR_WEIGHT", f"{p.weight_kg} kg" if p.weight_kg else "-", None),
            ("ATTR_PLAY_STYLES", p.play_style_tags if p.play_style_tags and p.play_style_tags != '-' else "None", None),
        ]
        col1_current_y = self._draw_attribute_group(surface_to_draw_on, level1_attrs_col1, col1_x, col1_current_y,
                                                    FONT_LEVEL_1, self.colors['text_normal'],
                                                    self.colors['text_normal'])

        # --- Column 2 Attributes (Base Attributes & Stats) ---
        col2_current_y = current_y
        is_gk = p.position.upper() == "GK"
        base_attr_labels_keys = [
            ("BASE_ATTR_PACE", "BASE_ATTR_DIVING"), ("BASE_ATTR_SHOOTING", "BASE_ATTR_HANDLING"),
            ("BASE_ATTR_PASSING", "BASE_ATTR_KICKING"), ("BASE_ATTR_DRIBBLING", "BASE_ATTR_REFLEXES"),
            ("BASE_ATTR_DEFENSE", "BASE_ATTR_SPEED_GK"), ("BASE_ATTR_PHYSICAL", "BASE_ATTR_POSITIONING_GK")
        ]
        base_attr_values = [
            p.base_attr1_val, p.base_attr2_val, p.base_attr3_val,
            p.base_attr4_val, p.base_attr5_val, p.base_attr6_val
        ]

        base_attr_grid_x_start = col2_x
        attr_box_visual_width = (main_rect.right - self.padding - base_attr_grid_x_start) // 3

        for i in range(6):
            label_key = base_attr_labels_keys[i][1] if is_gk else base_attr_labels_keys[i][0]
            value = base_attr_values[i]

            attr_center_x = base_attr_grid_x_start + (i % 3) * attr_box_visual_width + attr_box_visual_width // 2
            attr_y_base = col2_current_y + (i // 3) * (
                        self.attribute_line_height * 2.2)  # Increased vertical spacing for GK style boxes

            self._draw_attribute_group(surface_to_draw_on, [(label_key, value, label_key)],
                                       # Pass label_key as override for GK style
                                       attr_center_x, attr_y_base, FONT_LEVEL_3,
                                       self.colors['text_normal'], (180, 220, 180),
                                       is_base_attr_gk_style=True)

        col2_current_y += 2 * (self.attribute_line_height * 2.2) + self.section_spacing  # Update y after base attrs

        # Level 1: Stats (Below Base Attributes)
        stats_attrs = [
            ("ATTR_MATCHES_PLAYED", p.matches_played, None),
            ("ATTR_GOALS", p.goals_scored, None),
            ("ATTR_ASSISTS", p.assists_given, None),
        ]
        if is_gk or p.position.upper() in DEFENDERS:  # Assuming DEFENDERS is a set/list
            stats_attrs.append(("ATTR_CLEAN_SHEETS", p.clean_sheets, None))

        stats_attrs.extend([
            ("ATTR_AVG_RATING", f"{p.avg_rating:.2f}" if p.avg_rating != 0.0 else "-", None),
            ("ATTR_MOTM", p.motm_count, None),
            ("ATTR_YELLOW_CARDS", p.yellow_cards_received, None),
            ("ATTR_RED_CARDS", p.red_cards_received, None),
            ("ATTR_GROWTH", f"+{p.growth}" if p.growth > 0 else (str(p.growth) if p.growth < 0 else "0"), None),
            ("VALUE", f"{self.game.labels.get_currency_symbol()}{p.value:,}", None)  # Show value here too
        ])
        if p.is_on_transfer_list and p.asking_price is not None:
            stats_attrs.append(
                ("COL_ASKING_PRICE", f"{self.game.labels.get_currency_symbol()}{p.asking_price:,}", None))

        self._draw_attribute_group(surface_to_draw_on, stats_attrs, col2_x, col2_current_y, FONT_LEVEL_1,
                                   self.colors['text_normal'], self.colors['text_normal'])

    def _draw_confirmation_dialog(self, screen: pygame.Surface):
        pygame.draw.rect(screen, (40, 40, 50), self.confirmation_dialog_rect, border_radius=10)  # Darker panel
        pygame.draw.rect(screen, self.colors['active_button'], self.confirmation_dialog_rect, 2,
                         border_radius=10)  # Highlight border

        lines = self.confirmation_message.split('\n')
        msg_y = self.confirmation_dialog_rect.top + 25  # More padding
        line_height = self.font_medium.get_height() + 3

        for i, line in enumerate(lines):
            self.draw_text(screen, line,
                           (self.confirmation_dialog_rect.centerx, msg_y + i * line_height),
                           self.font_medium, self.colors['text_normal'], center_x=True)

        if self.confirm_yes_button: self.confirm_yes_button.draw(screen)
        if self.confirm_no_button: self.confirm_no_button.draw(screen)

    def _draw_asking_price_dialog(self, screen: pygame.Surface):
        pygame.draw.rect(screen, (40, 40, 50), self.asking_price_dialog_rect, border_radius=10)
        pygame.draw.rect(screen, self.colors['active_button'], self.asking_price_dialog_rect, 2, border_radius=10)

        prompt_text = self.game.labels.get_text("INPUT_ASKING_PRICE")
        self.draw_text(screen, prompt_text,
                       (self.asking_price_dialog_rect.centerx, self.asking_price_dialog_rect.top + 30),
                       self.font_medium, self.colors['text_normal'], center_x=True)

        if self.asking_price_input_box: self.asking_price_input_box.draw(screen)
        if self.asking_price_confirm_button: self.asking_price_confirm_button.draw(screen)
        if self.asking_price_cancel_button: self.asking_price_cancel_button.draw(screen)

        if self.error_message and self.message_timer > 0:
            msg_box_bottom = self.asking_price_input_box.rect.bottom if self.asking_price_input_box else self.asking_price_dialog_rect.centery
            self.draw_text(screen, self.error_message,
                           (self.asking_price_dialog_rect.centerx, msg_box_bottom + 15),
                           self.font_small, self.colors['error_text'], center_x=True)