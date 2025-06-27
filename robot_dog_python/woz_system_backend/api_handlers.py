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
    
    async def create_target(self, map_id: str, target_data: Dict, target_img_file: Optional[UploadFile] = None, env_img_file: Optional[UploadFile] = None) -> Dict:
        """在地图上创建新目标点"""
        try:
            # 检查地图是否存在
            query = "SELECT * FROM maps WHERE id = ?"
            rows = db.execute_query(query, (map_id,))
            if not rows:
                raise HTTPException(status_code=404, detail="Map not found")
            
            # 验证必需字段
            required_fields = ['targetName', 'pose']
            for field in required_fields:
                if field not in target_data or not target_data[field]:
                    raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
            
            # 解析pose数据
            try:
                if isinstance(target_data['pose'], str):
                    pose_data = json.loads(target_data['pose'])
                else:
                    pose_data = target_data['pose']
            except (json.JSONDecodeError, TypeError):
                raise HTTPException(status_code=400, detail="Invalid pose format")
            
            # 获取当前最大sequence值
            sequence_query = "SELECT MAX(sequence) as max_seq FROM ja_targets WHERE map_id = ?"
            sequence_rows = db.execute_query(sequence_query, (map_id,))
            max_sequence = sequence_rows[0]['max_seq'] if sequence_rows and sequence_rows[0]['max_seq'] is not None else 0
            new_sequence = max_sequence + 1
            
            target_id = db.generate_id()
            
            # 处理图片上传
            target_img_url = None
            env_img_url = None
            
            if target_img_file:
                file_content = await target_img_file.read()
                success, message, img_url = await file_handler.save_target_image(
                    file_content, target_img_file.filename, target_id, 'target'
                )
                if success:
                    target_img_url = img_url
                else:
                    logger.warning(f"Failed to save target image: {message}")
            
            if env_img_file:
                file_content = await env_img_file.read()
                success, message, img_url = await file_handler.save_target_image(
                    file_content, env_img_file.filename, target_id, 'environment'
                )
                if success:
                    env_img_url = img_url
                else:
                    logger.warning(f"Failed to save environment image: {message}")
            
            # 构建目标点数据
            target_full_data = {
                'description': target_data.get('description', ''),
                'pose': pose_data,
                'targetImgUrl': target_img_url,
                'envImgUrl': env_img_url
            }
            
            data_json = db.to_json(target_full_data)
            
            # 插入数据库
            query = "INSERT INTO ja_targets (id, map_id, name, data, sequence) VALUES (?, ?, ?, ?, ?)"
            db.execute_insert(query, (target_id, map_id, target_data['targetName'], data_json, new_sequence))
            
            result = {
                "targetId": target_id,
                "mapId": map_id,
                "targetName": target_data['targetName'],
                "description": target_full_data['description'],
                "sequence": new_sequence,
                "pose": pose_data,
                "targetImgUrl": target_img_url,
                "envImgUrl": env_img_url
            }
            
            logger.info(f"Created target: {target_id} for map: {map_id}")
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create target for map {map_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to create target")
    
    async def update_target(self, target_id: str, target_data: Dict, target_img_file: Optional[UploadFile] = None, env_img_file: Optional[UploadFile] = None) -> Dict:
        """更新目标点信息"""
        try:
            # 检查目标点是否存在
            query = "SELECT * FROM ja_targets WHERE id = ?"
            rows = db.execute_query(query, (target_id,))
            if not rows:
                raise HTTPException(status_code=404, detail="Target not found")
            
            existing_target = rows[0]
            existing_data = db.from_json(existing_target['data'])
            
            # 解析pose数据
            pose_data = existing_data.get('pose', {})
            if 'pose' in target_data:
                try:
                    if isinstance(target_data['pose'], str):
                        pose_data = json.loads(target_data['pose'])
                    else:
                        pose_data = target_data['pose']
                except (json.JSONDecodeError, TypeError):
                    raise HTTPException(status_code=400, detail="Invalid pose format")
            
            # 处理图片上传
            target_img_url = existing_data.get('targetImgUrl')
            env_img_url = existing_data.get('envImgUrl')
            
            if target_img_file:
                # 删除旧图片
                if target_img_url:
                    file_handler.delete_image(target_img_url)
                
                file_content = await target_img_file.read()
                success, message, img_url = await file_handler.save_target_image(
                    file_content, target_img_file.filename, target_id, 'target'
                )
                if success:
                    target_img_url = img_url
                else:
                    logger.warning(f"Failed to save target image: {message}")
            
            if env_img_file:
                # 删除旧图片
                if env_img_url:
                    file_handler.delete_image(env_img_url)
                
                file_content = await env_img_file.read()
                success, message, img_url = await file_handler.save_target_image(
                    file_content, env_img_file.filename, target_id, 'environment'
                )
                if success:
                    env_img_url = img_url
                else:
                    logger.warning(f"Failed to save environment image: {message}")
            
            # 更新数据
            updated_data = {
                'description': target_data.get('description', existing_data.get('description', '')),
                'pose': pose_data,
                'targetImgUrl': target_img_url,
                'envImgUrl': env_img_url
            }
            
            data_json = db.to_json(updated_data)
            target_name = target_data.get('targetName', existing_target['name'])
            
            query = "UPDATE ja_targets SET name = ?, data = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            affected_rows = db.execute_update(query, (target_name, data_json, target_id))
            
            if affected_rows == 0:
                raise HTTPException(status_code=404, detail="Target not found")
            
            result = {
                "targetId": target_id,
                "mapId": existing_target['map_id'],
                "targetName": target_name,
                "description": updated_data['description'],
                "sequence": existing_target['sequence'],
                "pose": pose_data,
                "targetImgUrl": target_img_url,
                "envImgUrl": env_img_url
            }
            
            logger.info(f"Updated target: {target_id}")
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to update target {target_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to update target")
    
    async def update_targets_order(self, map_id: str, target_ids: List[str]):
        """批量更新目标点顺序"""
        try:
            # 检查地图是否存在
            query = "SELECT * FROM maps WHERE id = ?"
            rows = db.execute_query(query, (map_id,))
            if not rows:
                raise HTTPException(status_code=404, detail="Map not found")
            
            # 验证所有目标点都属于该地图
            placeholders = ','.join(['?' for _ in target_ids])
            query = f"SELECT id FROM ja_targets WHERE id IN ({placeholders}) AND map_id = ?"
            params = target_ids + [map_id]
            existing_targets = db.execute_query(query, params)
            
            existing_target_ids = {row['id'] for row in existing_targets}
            if len(existing_target_ids) != len(target_ids):
                missing_targets = set(target_ids) - existing_target_ids
                raise HTTPException(status_code=400, detail=f"Invalid target IDs: {missing_targets}")
            
            # 批量更新顺序
            for index, target_id in enumerate(target_ids):
                sequence = index + 1
                query = "UPDATE ja_targets SET sequence = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
                db.execute_update(query, (sequence, target_id))
            
            logger.info(f"Updated targets order for map: {map_id}")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to update targets order for map {map_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to update targets order")
    
    async def delete_target(self, target_id: str):
        """删除目标点"""
        try:
            # 获取目标点信息
            query = "SELECT * FROM ja_targets WHERE id = ?"
            rows = db.execute_query(query, (target_id,))
            if not rows:
                raise HTTPException(status_code=404, detail="Target not found")
            
            target_data = db.from_json(rows[0]['data'])
            
            # 删除相关图片
            if target_data.get('targetImgUrl'):
                file_handler.delete_image(target_data['targetImgUrl'])
            if target_data.get('envImgUrl'):
                file_handler.delete_image(target_data['envImgUrl'])
            
            # 删除数据库记录
            query = "DELETE FROM ja_targets WHERE id = ?"
            affected_rows = db.execute_update(query, (target_id,))
            
            if affected_rows == 0:
                raise HTTPException(status_code=404, detail="Target not found")
            
            logger.info(f"Deleted target: {target_id}")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete target {target_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to delete target")


class TargetHandler:
    """目标点管理API处理器"""
    
    async def get_by_id(self, target_id: str) -> Dict:
        """根据ID获取目标点"""
        try:
            query = "SELECT * FROM ja_targets WHERE id = ?"
            rows = db.execute_query(query, (target_id,))
            
            if not rows:
                raise HTTPException(status_code=404, detail="Target not found")
            
            row = rows[0]
            target_data = db.from_json(row['data'])
            
            return {
                "targetId": row['id'],
                "mapId": row['map_id'],
                "targetName": row['name'],
                "description": target_data.get('description', ''),
                "sequence": row['sequence'],
                "pose": target_data.get('pose', {}),
                "targetImgUrl": target_data.get('targetImgUrl'),
                "envImgUrl": target_data.get('envImgUrl'),
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get target {target_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve target")


# 创建处理器实例
participant_handler = ParticipantHandler()
map_handler = MapHandler()
target_handler = TargetHandler()
