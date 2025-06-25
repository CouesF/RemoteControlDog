"""
WOZ系统API处理器 - 所有HTTP API端点的实现
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastapi import HTTPException, UploadFile, Form, File
import json

from .database import db
from .file_utils import file_handler
from .dds_bridge import dds_bridge

logger = logging.getLogger(__name__)


class ParticipantHandler:
    """被试管理API处理器"""
    
    async def get_all_participants(self) -> List[Dict]:
        """获取所有被试者"""
        try:
            query = "SELECT * FROM participants ORDER BY created_at DESC"
            rows = db.execute_query(query)
            
            participants = []
            for row in rows:
                participant_data = db.from_json(row['data'])
                participant = {
                    "participantId": row['id'],
                    "participantName": participant_data.get('participantName', ''),
                    "year": participant_data.get('year', 0),
                    "month": participant_data.get('month', 0),
                    "parentName": participant_data.get('parentName', ''),
                    "parentPhone": participant_data.get('parentPhone', ''),
                    "diagnosticInfo": participant_data.get('diagnosticInfo', ''),
                    "preferenceInfo": participant_data.get('preferenceInfo', ''),
                }
                participants.append(participant)
            
            return participants
            
        except Exception as e:
            logger.error(f"Failed to get participants: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve participants")
    
    async def get_participant_by_id(self, participant_id: str) -> Dict:
        """根据ID获取被试者"""
        try:
            query = "SELECT * FROM participants WHERE id = ?"
            rows = db.execute_query(query, (participant_id,))
            
            if not rows:
                raise HTTPException(status_code=404, detail="Participant not found")
            
            row = rows[0]
            participant_data = db.from_json(row['data'])
            
            return {
                "participantId": row['id'],
                "participantName": participant_data.get('participantName', ''),
                "year": participant_data.get('year', 0),
                "month": participant_data.get('month', 0),
                "parentName": participant_data.get('parentName', ''),
                "parentPhone": participant_data.get('parentPhone', ''),
                "diagnosticInfo": participant_data.get('diagnosticInfo', ''),
                "preferenceInfo": participant_data.get('preferenceInfo', ''),
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get participant {participant_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve participant")
    
    async def create_participant(self, participant_data: Dict) -> Dict:
        """创建新被试者"""
        try:
            # 基本验证
            required_fields = ['participantName', 'year', 'month', 'parentName', 'parentPhone']
            for field in required_fields:
                if field not in participant_data or not participant_data[field]:
                    raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
            
            participant_id = db.generate_id()
            data_json = db.to_json(participant_data)
            
            query = "INSERT INTO participants (id, name, data) VALUES (?, ?, ?)"
            db.execute_insert(query, (participant_id, participant_data['participantName'], data_json))
            
            # 返回创建的被试者信息
            result = {
                "participantId": participant_id,
                **participant_data
            }
            
            logger.info(f"Created participant: {participant_id}")
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create participant: {e}")
            raise HTTPException(status_code=500, detail="Failed to create participant")
    
    async def update_participant(self, participant_id: str, participant_data: Dict) -> Dict:
        """更新被试者信息"""
        try:
            # 检查被试者是否存在
            await self.get_participant_by_id(participant_id)
            
            data_json = db.to_json(participant_data)
            
            query = "UPDATE participants SET name = ?, data = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            affected_rows = db.execute_update(query, (participant_data['participantName'], data_json, participant_id))
            
            if affected_rows == 0:
                raise HTTPException(status_code=404, detail="Participant not found")
            
            result = {
                "participantId": participant_id,
                **participant_data
            }
            
            logger.info(f"Updated participant: {participant_id}")
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to update participant {participant_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to update participant")
    
    async def delete_participant(self, participant_id: str):
        """删除被试者"""
        try:
            # 检查被试者是否存在
            await self.get_participant_by_id(participant_id)
            
            # 删除相关图片
            file_handler.delete_participant_images(participant_id)
            
            # 删除数据库记录
            query = "DELETE FROM participants WHERE id = ?"
            affected_rows = db.execute_update(query, (participant_id,))
            
            if affected_rows == 0:
                raise HTTPException(status_code=404, detail="Participant not found")
            
            logger.info(f"Deleted participant: {participant_id}")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete participant {participant_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to delete participant")
    
    async def upload_participant_image(self, participant_id: str, image_file: UploadFile, image_type: str) -> Dict:
        """上传被试者图片"""
        try:
            # 检查被试者是否存在
            await self.get_participant_by_id(participant_id)
            
            # 读取文件内容
            file_content = await image_file.read()
            
            # 保存图片
            success, message, image_url = await file_handler.save_participant_image(
                file_content, image_file.filename, participant_id, image_type
            )
            
            if not success:
                raise HTTPException(status_code=400, detail=message)
            
            # 保存图片信息到数据库
            image_id = db.generate_id()
            query = "INSERT INTO participant_images (id, participant_id, image_url, image_type) VALUES (?, ?, ?, ?)"
            db.execute_insert(query, (image_id, participant_id, image_url, image_type))
            
            result = {
                "imageId": image_id,
                "participantId": participant_id,
                "imageUrl": image_url,
                "imageType": image_type
            }
            
            logger.info(f"Uploaded image for participant {participant_id}: {image_id}")
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to upload image for participant {participant_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to upload image")
    
    async def get_participant_images(self, participant_id: str) -> List[Dict]:
        """获取被试者的所有图片"""
        try:
            # 检查被试者是否存在
            await self.get_participant_by_id(participant_id)
            
            query = "SELECT * FROM participant_images WHERE participant_id = ? ORDER BY created_at DESC"
            rows = db.execute_query(query, (participant_id,))
            
            images = []
            for row in rows:
                image = {
                    "imageId": row['id'],
                    "participantId": row['participant_id'],
                    "imageUrl": row['image_url'],
                    "imageType": row['image_type']
                }
                images.append(image)
            
            return images
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get images for participant {participant_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve images")
    
    async def delete_image(self, image_id: str):
        """删除图片"""
        try:
            # 获取图片信息
            query = "SELECT * FROM participant_images WHERE id = ?"
            rows = db.execute_query(query, (image_id,))
            
            if not rows:
                raise HTTPException(status_code=404, detail="Image not found")
            
            image_url = rows[0]['image_url']
            
            # 删除文件
            success, message = file_handler.delete_image(image_url)
            if not success:
                logger.warning(f"Failed to delete image file: {message}")
            
            # 删除数据库记录
            query = "DELETE FROM participant_images WHERE id = ?"
            db.execute_update(query, (image_id,))
            
            logger.info(f"Deleted image: {image_id}")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete image {image_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to delete image")


class MapHandler:
    """地图管理API处理器"""
    
    async def get_all_maps(self) -> List[Dict]:
        """获取所有地图"""
        try:
            query = "SELECT * FROM maps ORDER BY created_at DESC"
            rows = db.execute_query(query)
            
            maps = []
            for row in rows:
                map_data = db.from_json(row['data'])
                map_info = {
                    "mapId": row['id'],
                    "mapName": row['name'],
                    "mapDescription": map_data.get('mapDescription', ''),
                }
                maps.append(map_info)
            
            return maps
            
        except Exception as e:
            logger.error(f"Failed to get maps: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve maps")
    
    async def create_map(self, map_data: Dict) -> Dict:
        """创建新地图"""
        try:
            required_fields = ['mapName']
            for field in required_fields:
                if field not in map_data or not map_data[field]:
                    raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
            
            map_id = db.generate_id()
            data_json = db.to_json(map_data)
            
            query = "INSERT INTO maps (id, name, data) VALUES (?, ?, ?)"
            db.execute_insert(query, (map_id, map_data['mapName'], data_json))
            
            result = {
                "mapId": map_id,
                "mapName": map_data['mapName'],
                "mapDescription": map_data.get('mapDescription', ''),
            }
            
            logger.info(f"Created map: {map_id}")
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create map: {e}")
            raise HTTPException(status_code=500, detail="Failed to create map")
    
    async def update_map(self, map_id: str, map_data: Dict) -> Dict:
        """更新地图信息"""
        try:
            # 检查地图是否存在
            query = "SELECT * FROM maps WHERE id = ?"
            rows = db.execute_query(query, (map_id,))
            if not rows:
                raise HTTPException(status_code=404, detail="Map not found")
            
            data_json = db.to_json(map_data)
            
            query = "UPDATE maps SET name = ?, data = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            affected_rows = db.execute_update(query, (map_data['mapName'], data_json, map_id))
            
            if affected_rows == 0:
                raise HTTPException(status_code=404, detail="Map not found")
            
            result = {
                "mapId": map_id,
                "mapName": map_data['mapName'],
                "mapDescription": map_data.get('mapDescription', ''),
            }
            
            logger.info(f"Updated map: {map_id}")
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to update map {map_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to update map")
    
    async def delete_map(self, map_id: str):
        """删除地图"""
        try:
            # 检查地图是否存在
            query = "SELECT * FROM maps WHERE id = ?"
            rows = db.execute_query(query, (map_id,))
            if not rows:
                raise HTTPException(status_code=404, detail="Map not found")
            
            # 删除相关的目标点图片
            target_query = "SELECT id FROM ja_targets WHERE map_id = ?"
            target_rows = db.execute_query(target_query, (map_id,))
            for target_row in target_rows:
                file_handler.delete_target_images(target_row['id'])
            
            # 删除数据库记录（级联删除会处理相关的目标点）
            query = "DELETE FROM maps WHERE id = ?"
            affected_rows = db.execute_update(query, (map_id,))
            
            if affected_rows == 0:
                raise HTTPException(status_code=404, detail="Map not found")
            
            logger.info(f"Deleted map: {map_id}")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete map {map_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to delete map")
    
    async def get_map_targets(self, map_id: str) -> List[Dict]:
        """获取地图的所有目标点"""
        try:
            # 检查地图是否存在
            query = "SELECT * FROM maps WHERE id = ?"
            rows = db.execute_query(query, (map_id,))
            if not rows:
                raise HTTPException(status_code=404, detail="Map not found")
            
            query = "SELECT * FROM ja_targets WHERE map_id = ? ORDER BY sequence, created_at"
            rows = db.execute_query(query, (map_id,))
            
            targets = []
            for row in rows:
                target_data = db.from_json(row['data'])
                target = {
                    "targetId": row['id'],
                    "mapId": row['map_id'],
                    "targetName": row['name'],
                    "description": target_data.get('description', ''),
                    "sequence": row['sequence'],
                    "pose": target_data.get('pose', {}),
                    "targetImgUrl": target_data.get('targetImgUrl'),
                    "envImgUrl": target_data.get('envImgUrl'),
                }
                targets.append(target)
            
            return targets
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get targets for map {map_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve targets")


# 创建处理器实例
participant_handler = ParticipantHandler()
map_handler = MapHandler()
