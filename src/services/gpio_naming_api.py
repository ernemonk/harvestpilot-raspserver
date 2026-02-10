"""
GPIO Naming API - REST endpoints for safe GPIO name management

Endpoints:
  GET  /api/gpio/{pin}/info          - Get GPIO pin info including name status
  POST /api/gpio/{pin}/rename        - Rename a GPIO pin (mark as customized)
  POST /api/gpio/{pin}/reset-name    - Reset name to smart default
"""

import logging
from typing import Dict, Optional, Any
import asyncio

logger = logging.getLogger(__name__)


class GPIONamingAPI:
    """API handler for GPIO naming operations"""
    
    def __init__(self, gpio_controller):
        """
        Initialize the naming API with a GPIO controller instance.
        
        Args:
            gpio_controller: GPIOActuatorController instance
        """
        self.gpio_controller = gpio_controller
    
    async def get_gpio_info(self, gpio_number: int) -> Dict[str, Any]:
        """
        Get detailed information about a GPIO pin including naming status.
        
        Returns info about:
          - GPIO number and physical pin
          - Current name and default name
          - Whether name is user-customized
          - When it was customized (if applicable)
          - Current state (desired vs hardware)
        
        Args:
            gpio_number: GPIO number
            
        Returns:
            Dictionary with GPIO info or error dict
        """
        try:
            info = self.gpio_controller.get_gpio_info(gpio_number)
            
            if not info:
                return {
                    "error": f"GPIO {gpio_number} not found",
                    "gpio_number": gpio_number
                }
            
            return {
                "success": True,
                "gpio": info
            }
            
        except Exception as e:
            logger.error(f"Error getting GPIO{gpio_number} info: {e}")
            return {
                "error": f"Failed to get GPIO info: {str(e)}",
                "gpio_number": gpio_number
            }
    
    async def rename_gpio(self, gpio_number: int, new_name: str) -> Dict[str, Any]:
        """
        Rename a GPIO pin and mark it as user-customized.
        
        CRITICAL: This operation marks the name as user-customized, which
        means future initializations will NOT overwrite it. This is permanent
        until explicitly reset.
        
        Args:
            gpio_number: GPIO number
            new_name: New name for the GPIO
            
        Returns:
            Dictionary with operation result
        """
        try:
            if not new_name or not new_name.strip():
                return {
                    "error": "Name cannot be empty",
                    "gpio_number": gpio_number
                }
            
            success = self.gpio_controller.rename_gpio_pin(gpio_number, new_name.strip())
            
            if success:
                # Get updated info
                info = self.gpio_controller.get_gpio_info(gpio_number)
                return {
                    "success": True,
                    "message": f"GPIO{gpio_number} renamed successfully",
                    "gpio": info
                }
            else:
                return {
                    "error": f"Failed to rename GPIO{gpio_number}",
                    "gpio_number": gpio_number
                }
                
        except Exception as e:
            logger.error(f"Error renaming GPIO{gpio_number}: {e}")
            return {
                "error": f"Failed to rename GPIO: {str(e)}",
                "gpio_number": gpio_number
            }
    
    async def reset_gpio_name_to_default(self, gpio_number: int) -> Dict[str, Any]:
        """
        Reset a GPIO pin name to the smart default.
        
        This operation:
          1. Removes the custom name
          2. Regenerates the smart default based on GPIO + capabilities
          3. Removes the user-customized flag
        
        Args:
            gpio_number: GPIO number
            
        Returns:
            Dictionary with operation result
        """
        try:
            success = self.gpio_controller.reset_gpio_name_to_default(gpio_number)
            
            if success:
                # Get updated info
                info = self.gpio_controller.get_gpio_info(gpio_number)
                return {
                    "success": True,
                    "message": f"GPIO{gpio_number} name reset to smart default",
                    "gpio": info
                }
            else:
                return {
                    "error": f"Failed to reset GPIO{gpio_number} name",
                    "gpio_number": gpio_number
                }
                
        except Exception as e:
            logger.error(f"Error resetting GPIO{gpio_number} name: {e}")
            return {
                "error": f"Failed to reset GPIO name: {str(e)}",
                "gpio_number": gpio_number
            }
    
    async def get_all_gpio_info(self) -> Dict[str, Any]:
        """
        Get information about all GPIO pins.
        
        Returns:
            Dictionary with all GPIO pins and their info
        """
        try:
            pin_states = self.gpio_controller.get_pin_states()
            
            all_info = {
                "total_pins": len(pin_states),
                "pins": {}
            }
            
            for pin, state in pin_states.items():
                info = self.gpio_controller.get_gpio_info(pin)
                if info:
                    all_info["pins"][str(pin)] = info
            
            return {
                "success": True,
                "gpios": all_info
            }
            
        except Exception as e:
            logger.error(f"Error getting all GPIO info: {e}")
            return {
                "error": f"Failed to get GPIO info: {str(e)}"
            }
    
    async def batch_rename_gpios(self, renames: Dict[int, str]) -> Dict[str, Any]:
        """
        Rename multiple GPIO pins at once.
        
        Args:
            renames: Dictionary mapping GPIO numbers to new names
            
        Returns:
            Dictionary with results for each GPIO
        """
        results = {
            "total": len(renames),
            "successful": 0,
            "failed": 0,
            "pins": {}
        }
        
        for gpio_num, new_name in renames.items():
            try:
                success = self.gpio_controller.rename_gpio_pin(gpio_num, new_name)
                
                if success:
                    results["successful"] += 1
                    results["pins"][gpio_num] = {
                        "success": True,
                        "new_name": new_name
                    }
                else:
                    results["failed"] += 1
                    results["pins"][gpio_num] = {
                        "success": False,
                        "error": "Rename operation failed"
                    }
                    
            except Exception as e:
                results["failed"] += 1
                results["pins"][gpio_num] = {
                    "success": False,
                    "error": str(e)
                }
        
        return {
            "success": results["failed"] == 0,
            "results": results
        }


# Factory function to create the API
def create_gpio_naming_api(gpio_controller) -> GPIONamingAPI:
    """Create a GPIO Naming API instance"""
    return GPIONamingAPI(gpio_controller)
