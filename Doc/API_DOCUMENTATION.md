# 机器人辅助训练WOZ系统 - HTTP API文档

**版本: 1.0.0**

## 简介

本文档定义了用于机器人辅助训练Wizard-of-Oz (WOZ)系统的前端（Electron应用）与后端（运行于机器狗主机）之间的HTTP API。该API旨在实现前后端的完全解耦，支持对被试、地图、实验会话及相关数据的全面管理。

---

## 1. 全局数据模型 (Data Models)

这些是在API请求和响应中使用的核心TypeScript/JSON对象结构。

```typescript
// 姿态
interface Pose {
    position: { x: number; y: number; z: number; };
    orientation: { w: number; qx: number; qy: number; qz: number; };
}

// 被试者信息
interface Participant {
    participantId: string; // UUID
    participantName: string;
    year: number;
    month: number;
    parentName: string;
    parentPhone: string;
    diagnosticInfo: string;
    preferenceInfo: string;
}

// 被试者图片信息
interface ParticipantImage {
    imageId: string; // UUID
    participantId:string;
    imageUrl: string; // 访问图片的URL
    imageType: 'participant' | 'parent' | 'other';
}

// 地图信息
interface MapInfo {
    mapId: string; // UUID
    mapName: string;
    mapDescription: string;
}

// RJA 目标点信息
interface JaTarget {
    targetId: string; // UUID
    mapId: string;
    targetName: string;
    description: string;
    sequence: number; // 用于排序
    pose: Pose;
    targetImgUrl?: string;
    envImgUrl?: string;
}

// 实验会话
interface Session {
    sessionId: string; // UUID
    participantId: string;
    mapId: string;
    startTime: string; // ISO 8601
    endTime?: string; // ISO 8601
    status: 'started' | 'paused' | 'ended';
}

// 单次指令/交互
interface Instruction {
    instructionId: string; // UUID
    sessionId: string;
    targetId: string;
    creationTime: string; // ISO 8601
    prompts: PromptAttempt[];
    finalOutcome: 'success' | 'failure' | 'unknown'; // 由后端根据prompts计算
}

// 单次指令中的某一级提示
interface PromptAttempt {
    promptId: string; // UUID
    level: 1 | 2 | 3;
    timestamp: string; // ISO 8601
    status: 'success' | 'failure';
}
```

---

## 2. API端点参考

### 2.1 被试管理 (Participants)

#### `GET /api/participants`
- **描述**: 获取所有被试者的列表。
- **返回 (200 OK)**: `application/json`
  ```json
  [
    {
      "participantId": "uuid-p1",
      "participantName": "张三",
      ...
    }
  ]
  ```

#### `POST /api/participants`
- **描述**: 创建一个新的被试。
- **请求体**: `application/json` - `Omit<Participant, 'participantId'>`
- **返回 (201 Created)**: `application/json` - `Participant` (包含新生成的 `participantId`)

#### `PUT /api/participants/{participantId}`
- **描述**: 更新一个已存在的被试信息。
- **请求体**: `application/json` - `Participant`
- **返回 (200 OK)**: `application/json` - `Participant` (更新后的信息)

#### `DELETE /api/participants/{participantId}`
- **描述**: 删除一个被试。
- **返回 (204 No Content)**

---

### 2.2 图片管理 (Images)

#### `POST /api/participants/{participantId}/images`
- **描述**: 为指定被试上传一张图片。
- **请求体**: `multipart/form-data`
  - `imageFile`: (file) 图片文件
  - `imageType`: (string) `'participant'` 或 `'parent'`
- **返回 (201 Created)**: `application/json` - `ParticipantImage`

#### `GET /api/participants/{participantId}/images`
- **描述**: 获取某被试的所有图片信息。
- **返回 (200 OK)**: `application/json` - `[ParticipantImage]`

#### `DELETE /api/images/{imageId}`
- **描述**: 删除一张指定的图片。
- **返回 (204 No Content)**

---

### 2.3 地图与目标点管理 (Maps & JA Targets)

#### `GET /api/maps`
- **描述**: 获取所有地图的列表。
- **返回 (200 OK)**: `application/json` - `[MapInfo]`

#### `POST /api/maps`
- **描述**: 创建新地图。
- **请求体**: `application/json` - `{ "mapName": string, "mapDescription": string }`
- **返回 (201 Created)**: `application/json` - `MapInfo`

#### `PUT /api/maps/{mapId}`
- **描述**: 更新地图信息。
- **请求体**: `application/json` - `{ "mapName": string, "mapDescription": string }`
- **返回 (200 OK)**: `application/json` - `MapInfo`

#### `DELETE /api/maps/{mapId}`
- **描述**: 删除地图及其下所有目标点。
- **返回 (204 No Content)**

#### `GET /api/maps/{mapId}/targets`
- **描述**: 获取指定地图的所有RJA目标点（按`sequence`排序）。
- **返回 (200 OK)**: `application/json` - `[JaTarget]`

#### `POST /api/maps/{mapId}/targets`
- **描述**: 在地图上创建新目标点。
- **请求体**: `multipart/form-data`
  - `targetName`: (string)
  - `description`: (string)
  - `pose`: (JSON string) e.g., `'{"position":{"x":1,"y":2,"z":0},"orientation":{"w":1,"qx":0,"qy":0,"qz":0}}'`
  - `targetImgFile`: (file, optional)
  - `envImgFile`: (file, optional)
- **返回 (201 Created)**: `application/json` - `JaTarget`

#### `PUT /api/targets/{targetId}`
- **描述**: 更新目标点信息。
- **请求体**: `multipart/form-data` (同上)
- **返回 (200 OK)**: `application/json` - `JaTarget`

#### `PUT /api/maps/{mapId}/targets/order`
- **描述**: 批量更新目标点的顺序。
- **请求体**: `application/json` - `{ "targetIds": ["uuid-t3", "uuid-t1", "uuid-t2"] }`
- **返回 (200 OK)**

#### `DELETE /api/targets/{targetId}`
- **描述**: 删除一个目标点。
- **返回 (204 No Content)**

---

### 2.4 实验流程管理 (Session Flow)

#### `POST /api/sessions`
- **描述**: 开始一次新的实验，创建会话。
- **请求体**: `application/json` - `{ "participantId": string, "mapId": string }`
- **返回 (201 Created)**: `application/json` - `Session`

#### `PUT /api/sessions/{sessionId}/status`
- **描述**: 更新会话状态。
- **请求体**: `application/json` - `{ "status": "paused" | "ended" }`
- **返回 (200 OK)**: `application/json` - `Session`

#### `POST /api/sessions/{sessionId}/instructions`
- **描述**: 在会话中开始一次新的指令交互。
- **请求体**: `application/json` - `{ "targetId": string }`
- **返回 (201 Created)**: `application/json` - `Instruction`

#### `POST /api/instructions/{instructionId}/prompts`
- **描述**: 记录一次具体等级的提示尝试及其结果。这是更新指令状态的核心。
- **请求体**: `application/json` - `{ "level": 1 | 2 | 3, "status": "success" | "failure" }`
- **返回 (201 Created)**: `application/json` - `Instruction` (返回更新后的整个指令对象)

#### `POST /api/sessions/{sessionId}/actions`
- **描述**: 在实验中触发一个特殊事件或动作。
- **请求体**: `application/json`
  ```json
  {
    "actionType": "GENERATE_SPEECH",
    "payload": {
      "text": "张三，请跟上我哦"
    }
  }
  ```
  或
  ```json
  {
    "actionType": "LOG_EVENT",
    "payload": {
      "eventName": "PARTICIPANT_LOST",
      "details": "Participant out of frame for 5 seconds."
    }
  }
  ```
- **Action Types**:
  - `GENERATE_SPEECH`: 请求后端合成并播放语音。
  - `LOG_EVENT`: 记录一个不一定触发动作的事件。
- **返回 (202 Accepted)**

---

## 3. 建议数据库表结构 (SQLite)

(此部分为后端实现建议，非API契约)

- **`Participants`**: `participant_id`, `participant_name`, `year`, `month`, `parent_name`, `parent_phone`, `diagnostic_info`, `preference_info`
- **`Participant_Images`**: `image_id`, `participant_id`, `image_url`, `image_type`
- **`Maps`**: `map_id`, `map_name`, `map_description`
- **`JA_Targets`**: `target_id`, `map_id`, `target_name`, `description`, `sequence`, `pose_x`, `pose_y`, `pose_z`, `pose_qw`, `pose_qx`, `pose_qy`, `pose_qz`, `target_img_url`, `env_img_url`
- **`Sessions`**: `session_id`, `participant_id`, `map_id`, `start_time`, `end_time`, `status`
- **`Instructions`**: `instruction_id`, `session_id`, `target_id`, `creation_time`, `final_outcome`
- **`Prompt_Attempts`**: `prompt_id`, `instruction_id`, `level`, `timestamp`, `status`
- **`Event_Logs`**: `log_id`, `session_id`, `timestamp`, `event_name`, `event_detail` (JSON)
