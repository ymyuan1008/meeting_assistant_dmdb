// 前端密码加密示例代码

// 1. 获取公钥
async function getPublicKey() {
    try {
        const response = await fetch('/api/auth/public-key');
        const data = await response.json();
        return data.public_key;
    } catch (error) {
        console.error('获取公钥失败:', error);
        throw error;
    }
}

// 2. 使用JSEncrypt库进行RSA加密
// 注意：需要先引入JSEncrypt库
// <script src="https://cdnjs.cloudflare.com/ajax/libs/jsencrypt/3.0.0-beta.1/jsencrypt.min.js"></script>

async function encryptPassword(password) {
    try {
        // 获取公钥
        const publicKey = await getPublicKey();
        
        // 使用JSEncrypt进行加密
        const encrypt = new JSEncrypt();
        encrypt.setPublicKey(publicKey);
        const encrypted = encrypt.encrypt(password);
        
        return encrypted;
    } catch (error) {
        console.error('密码加密失败:', error);
        throw error;
    }
}

// 3. 登录示例
async function login(username, password) {
    try {
        // 加密密码
        const encryptedPassword = await encryptPassword(password);
        
        // 发送登录请求
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                username: username,
                password: encryptedPassword
            })
        });
        
        const result = await response.json();
        return result;
    } catch (error) {
        console.error('登录失败:', error);
        throw error;
    }
}

// 4. 注册示例
async function register(userData) {
    try {
        // 加密密码
        const encryptedPassword = await encryptPassword(userData.password);
        
        // 发送注册请求
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                ...userData,
                password: encryptedPassword
            })
        });
        
        const result = await response.json();
        return result;
    } catch (error) {
        console.error('注册失败:', error);
        throw error;
    }
}

// 使用示例
/*
// 登录
login('testuser', 'Test@1234')
    .then(result => {
        if (result.code === 200) {
            console.log('登录成功', result.data);
        } else {
            console.log('登录失败', result.message);
        }
    });

// 注册
register({
    name: '测试用户',
    user_name: 'testuser',
    password: 'Test@1234',
    email: 'test@example.com'
})
    .then(result => {
        if (result.code === 0) {
            console.log('注册成功', result.data);
        } else {
            console.log('注册失败', result.message);
        }
    });
*/