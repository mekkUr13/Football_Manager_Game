import pygame

class InputBox:
    """An editable text input box with cursor, selection, and scrolling."""
    def __init__(self, x, y, w, h, font, text='', placeholder='', is_password=False):
        self.rect = pygame.Rect(x, y, w, h)
        self.font = font
        self.text = str(text) # Ensure text is initially a string
        self.placeholder = placeholder
        self.is_password = is_password
        self.active = False

        # Colors
        self.color_inactive = pygame.Color('lightskyblue3')
        self.color_active = pygame.Color('dodgerblue2')
        self.color_text = pygame.Color('black')
        self.color_placeholder = pygame.Color('gray50')
        self.color_selection = pygame.Color(170, 200, 255) # Light blue for selection
        self.color_border = self.color_inactive # Initial border color

        # State
        self.cursor_pos = len(self.text) # Cursor starts at the end
        self.scroll_offset_x = 0
        self.selection_start = -1 # Index where selection starts, -1 if no selection
        self.selecting = False # True if mouse is being dragged for selection

        # Cursor Blink Timing
        self.cursor_visible = False
        self.cursor_timer = 0.0
        self.cursor_blink_interval = 0.5 # seconds

        # Render initial text/placeholder
        self.txt_surface = self._render_text_surface()

    def _render_text_surface(self):
        """Renders the text (or placeholder or password stars) to a pygame Surface."""
        display_string = ""
        color = self.color_text  # Default text color

        if not self.text and not self.active:
            # Show placeholder only if inactive AND empty
            display_string = self.placeholder
            color = self.color_placeholder
        elif self.is_password:
            # If it's a password field, always show stars *regardless of active state*
            # The checkbox toggle handles the actual switching by setting is_password
            display_string = '*' * len(self.text)
        else:
            # Otherwise, show the actual text
            display_string = self.text

        try:
            return self.font.render(display_string, True, color)
        except Exception as e:
            print(f"Error rendering input text: {e}")
            return self.font.render("!", True, (255, 0, 0))  # Fallback surface


    def _get_char_pos_from_mouse(self, mouse_x):
        """Calculates the text index corresponding to a mouse X coordinate."""
        relative_x = mouse_x - (self.rect.x + 5 - self.scroll_offset_x) # 5 is padding
        current_x = 0
        for i in range(len(self.text) + 1):
            # Get width up to index i
            try:
                 char_width = self.font.size(self.text[:i])[0]
            except: # Handle potential font errors
                 char_width = i * 8 # Estimate width if font fails
            # If mouse is between the previous char and this one
            if relative_x < char_width:
                # Check midpoint to decide which index is closer
                prev_width = self.font.size(self.text[:i-1])[0] if i > 0 else 0
                if abs(relative_x - prev_width) <= abs(relative_x - char_width):
                    return max(0, i - 1)
                else:
                    return i
        return len(self.text) # If beyond the end

    def _ensure_cursor_visible(self):
         """Adjusts scroll_offset_x to make the cursor visible."""
         padding = 5
         visible_width = self.rect.width - 2 * padding
         try:
              cursor_pixel_x = self.font.size(self.text[:self.cursor_pos])[0]
         except:
              cursor_pixel_x = self.cursor_pos * 8 # Estimate

         # If cursor is left of the visible area
         if cursor_pixel_x < self.scroll_offset_x:
             self.scroll_offset_x = cursor_pixel_x
         # If cursor is right of the visible area
         elif cursor_pixel_x > self.scroll_offset_x + visible_width:
             self.scroll_offset_x = cursor_pixel_x - visible_width

         # Clamp scroll offset
         max_scroll = max(0, self.txt_surface.get_width() - visible_width)
         self.scroll_offset_x = max(0, min(self.scroll_offset_x, max_scroll))


    def _get_selection(self):
        """Returns the start and end indices of the current selection, ordered."""
        if self.selection_start == -1:
            return -1, -1
        # Ensure start is always less than or equal to end
        start = min(self.selection_start, self.cursor_pos)
        end = max(self.selection_start, self.cursor_pos)
        return start, end

    def _delete_selection(self):
        """Deletes the selected text and returns True if something was deleted."""
        start, end = self._get_selection()
        if start != -1:
            self.text = self.text[:start] + self.text[end:]
            self.cursor_pos = start # Move cursor to deletion start
            self.selection_start = -1 # Clear selection
            return True
        return False

    def handle_event(self, event):
        # --- Mouse Button Down ---
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                if not self.active:
                    self.active = True
                    self.cursor_pos = self._get_char_pos_from_mouse(event.pos[0])
                    self._ensure_cursor_visible()
                self.selecting = True
                self.selection_start = self._get_char_pos_from_mouse(event.pos[0])
                self.cursor_pos = self.selection_start # Start selection drag from click point
                self._ensure_cursor_visible()
            else:
                self.active = False
                self.selecting = False
                self.selection_start = -1 # Clear selection if clicking outside
            # Update color and re-render (might show/hide placeholder)
            self.color_border = self.color_active if self.active else self.color_inactive
            self.txt_surface = self._render_text_surface()

        # --- Mouse Button Up ---
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.selecting = False
            # If selection start and end are same, clear selection
            if self.selection_start == self.cursor_pos:
                 self.selection_start = -1

        # --- Mouse Motion (for text selection) ---
        elif event.type == pygame.MOUSEMOTION:
            if self.active and self.selecting:
                 # Update cursor position based on drag
                 self.cursor_pos = self._get_char_pos_from_mouse(event.pos[0])
                 self._ensure_cursor_visible()

        # --- Key Down ---
        elif event.type == pygame.KEYDOWN:
            if self.active:
                processed = False # Flag to track if the key was processed
                mods = pygame.key.get_mods()
                ctrl_pressed = mods & pygame.KMOD_CTRL
                shift_pressed = mods & pygame.KMOD_SHIFT  # Keep track of shift

                # --- Handle specific key actions first ---
                if event.key == pygame.K_LEFT:
                    if ctrl_pressed:
                        pos = self.text.rfind(' ', 0,
                                              self.cursor_pos); self.cursor_pos = pos + 1 if pos != -1 else 0
                    else:
                        self.cursor_pos = max(0, self.cursor_pos - 1)
                    if not shift_pressed:
                        self.selection_start = -1
                    elif self.selection_start == -1:
                        self.selection_start = self.cursor_pos + 1
                    self._ensure_cursor_visible()
                    processed = True  # Mark key as processed

                elif event.key == pygame.K_RIGHT:
                    if ctrl_pressed:
                        pos = self.text.find(' ', self.cursor_pos); self.cursor_pos = pos if pos != -1 else len(
                            self.text)
                    else:
                        self.cursor_pos = min(len(self.text), self.cursor_pos + 1)
                    if not shift_pressed:
                        self.selection_start = -1
                    elif self.selection_start == -1:
                        self.selection_start = self.cursor_pos - 1
                    self._ensure_cursor_visible()
                    processed = True  # Mark key as processed

                elif event.key == pygame.K_HOME:
                    # ... (Home logic) ...
                    self.cursor_pos = 0
                    if not shift_pressed:
                        self.selection_start = -1
                    elif self.selection_start == -1:
                        self.selection_start = len(self.text)
                    self._ensure_cursor_visible()
                    processed = True  # Mark key as processed

                elif event.key == pygame.K_END:
                    # ... (End logic) ...
                    self.cursor_pos = len(self.text)
                    if not shift_pressed:
                        self.selection_start = -1
                    elif self.selection_start == -1:
                        self.selection_start = 0
                    self._ensure_cursor_visible()
                    processed = True  # Mark key as processed

                elif event.key == pygame.K_BACKSPACE:
                    # ... (Backspace logic) ...
                    if not self._delete_selection():
                        if self.cursor_pos > 0:
                            self.text = self.text[:self.cursor_pos - 1] + self.text[self.cursor_pos:]
                            self.cursor_pos -= 1
                    self._ensure_cursor_visible()
                    processed = True  # Mark key as processed

                elif event.key == pygame.K_DELETE:
                    # ... (Delete logic) ...
                    if not self._delete_selection():
                        if self.cursor_pos < len(self.text):
                            self.text = self.text[:self.cursor_pos] + self.text[self.cursor_pos + 1:]
                    self._ensure_cursor_visible()
                    processed = True  # Mark key as processed

                elif event.key == pygame.K_a and ctrl_pressed:
                    # ... (Select All logic) ...
                    self.selection_start = 0
                    self.cursor_pos = len(self.text)
                    processed = True  # Mark key as processed

                # --- Handle Character Input ---
                # Check event.unicode AFTER handling specific key actions
                # Use elif to avoid processing character input if a special key was handled
                elif event.key != pygame.K_TAB and event.unicode and not processed:
                    # Block only specific unwanted modifier combinations IF necessary
                    # Usually blocking all ctrl/alt/meta is too broad
                    # Let's allow most unicode characters through for now.

                    is_unwanted_combo = ctrl_pressed and event.key not in (pygame.K_c, pygame.K_v, pygame.K_x)

                    if not is_unwanted_combo:
                        # Delete selection before inserting
                        start, end = self._get_selection()
                        if start != -1:
                            self.text = self.text[:start] + self.text[end:]
                            self.cursor_pos = start
                            self.selection_start = -1

                        # Insert character
                        self.text = self.text[:self.cursor_pos] + event.unicode + self.text[self.cursor_pos:]
                        self.cursor_pos += len(event.unicode)
                        self._ensure_cursor_visible()
                        processed = True  # Mark as processed

                # --- Final Updates ---
                if processed:  # Only update if a relevant key was handled
                    self.txt_surface = self._render_text_surface()
                    self._ensure_cursor_visible()
                    self.cursor_timer = 0


    def update(self, dt):
         """Updates cursor blink state."""
         if self.active:
            self.cursor_timer += dt
            if self.cursor_timer >= self.cursor_blink_interval:
                self.cursor_visible = not self.cursor_visible
                self.cursor_timer %= self.cursor_blink_interval # Use modulo for smoother timing
         else:
            self.cursor_visible = False

    def draw(self, screen):
        """Draws the input box, text, selection, and cursor."""
        # Draw background and border
        pygame.draw.rect(screen, pygame.Color('white'), self.rect) # Always white background?
        self.color_border = self.color_active if self.active else self.color_inactive
        pygame.draw.rect(screen, self.color_border, self.rect, 2)

        # Define text area with padding
        text_area_rect = self.rect.inflate(-10, -10) # 5px padding each side

        # --- Draw Selection Background ---
        sel_start, sel_end = self._get_selection()
        if sel_start != -1:
             try:
                  # Calculate pixel coordinates for selection start/end
                  start_px = self.font.size(self.text[:sel_start])[0]
                  end_px = self.font.size(self.text[:sel_end])[0]
                  # Selection rect relative to text_area_rect origin, adjusted for scroll
                  sel_rect = pygame.Rect(
                      text_area_rect.left + start_px - self.scroll_offset_x,
                      text_area_rect.top,
                      end_px - start_px,
                      text_area_rect.height
                  )
                  # Clip selection rect to the visible text area
                  sel_rect_clipped = sel_rect.clip(text_area_rect)
                  pygame.draw.rect(screen, self.color_selection, sel_rect_clipped)
             except Exception as e:
                  print(f"Error drawing selection: {e}") # Catch potential font errors


        # --- Blit Text Surface (respecting scroll and clipping) ---
        source_rect = pygame.Rect(
            self.scroll_offset_x, 0,
            text_area_rect.width, self.txt_surface.get_height()
        )
        dest_pos = text_area_rect.topleft

        screen.set_clip(text_area_rect) # IMPORTANT: Clip *before* drawing text
        screen.blit(self.txt_surface, dest_pos, area=source_rect)
        screen.set_clip(None) # IMPORTANT: Reset clip *after* drawing text

        # --- Draw Blinking Cursor ---
        if self.active and self.cursor_visible:
             try:
                  # Calculate cursor x position relative to text start
                  cursor_pixel_x = self.font.size(self.text[:self.cursor_pos])[0]
                  # Position relative to screen, adjusted for scroll
                  cursor_screen_x = text_area_rect.left + cursor_pixel_x - self.scroll_offset_x
                  # Draw cursor only if it's within the visible text area
                  if text_area_rect.left <= cursor_screen_x <= text_area_rect.right:
                       pygame.draw.line(screen, self.color_text,
                                        (cursor_screen_x, text_area_rect.top),
                                        (cursor_screen_x, text_area_rect.bottom), 1)
             except Exception as e:
                  print(f"Error drawing cursor: {e}") # Catch font errors

    def get_text(self):
         """Returns the current text content."""
         return self.text

    def update_placeholder(self, new_placeholder: str):
        """Updates the placeholder text and re-renders if necessary."""
        if self.placeholder != new_placeholder:
            self.placeholder = new_placeholder
            # Re-render only if currently showing the placeholder
            if not self.text and not self.active:
                self.txt_surface = self._render_text_surface()

    def update_text(self, new_text: str):
         """Sets the text content directly and updates rendering."""
         self.text = str(new_text)
         self.cursor_pos = len(self.text) # Move cursor to end
         self.selection_start = -1 # Clear selection
         self.scroll_offset_x = 0 # Reset scroll might be needed
         self.txt_surface = self._render_text_surface()
         self._ensure_cursor_visible() # Adjust scroll if needed

class Checkbox:
    """A simple checkbox UI element."""
    def __init__(self, x, y, size, label, font, initial_checked=False):
        self.rect = pygame.Rect(x, y, size, size)
        self.checked = initial_checked
        self.label = label
        self.font = font
        self.label_surface = self.font.render(self.label, True, (220, 220, 220)) # Assuming light text color
        self.label_rect = self.label_surface.get_rect(left=self.rect.right + 10, centery=self.rect.centery)
        self.hover = False

    def handle_event(self, event):
        """Handle mouse clicks to toggle the checkbox."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Allow clicking on box or label
            clickable_area = self.rect.union(self.label_rect)
            if clickable_area.collidepoint(event.pos):
                self.checked = not self.checked
                return True # Event handled
        return False

    def check_hover(self, pos):
        """Update hover state."""
        clickable_area = self.rect.union(self.label_rect)
        self.hover = clickable_area.collidepoint(pos)


    def draw(self, screen):
        """Draw the checkbox and its label."""
        # Box style
        box_color = (200, 200, 200)
        border_color = (100, 100, 100) if not self.hover else (255, 255, 0) # Highlight on hover
        check_color = (0, 0, 0) # Color of the checkmark

        pygame.draw.rect(screen, box_color, self.rect)
        pygame.draw.rect(screen, border_color, self.rect, 2)

        # Draw checkmark if checked
        if self.checked:
            pygame.draw.line(screen, check_color, (self.rect.left + 3, self.rect.centery), (self.rect.centerx - 1, self.rect.bottom - 3), 2)
            pygame.draw.line(screen, check_color, (self.rect.centerx - 1, self.rect.bottom - 3), (self.rect.right - 3, self.rect.top + 3), 2)

        # Draw label
        if hasattr(self, 'label_surface') and self.label_surface:  # Check if surface exists
            screen.blit(self.label_surface, self.label_rect)

    def get_value(self):
        """Return the checked state."""
        return self.checked

    def update_label(self, new_label_text):
        """Updates the label text and re-renders the label surface."""
        if self.label != new_label_text:
            self.label = new_label_text
            try:
                # Re-render the label surface with the new text
                self.label_surface = self.font.render(self.label, True, (220, 220, 220))
                # Update label rect position based on new surface size
                self.label_rect = self.label_surface.get_rect(left=self.rect.right + 10, centery=self.rect.centery)
            except Exception as e:
                print(f"Error updating checkbox label '{self.label}': {e}")
                # Create a dummy surface on error
                self.label_surface = self.font.render("?", True, (255, 0, 0))
                self.label_rect = self.label_surface.get_rect(left=self.rect.right + 10, centery=self.rect.centery)