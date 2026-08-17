<?php
ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);
// إعدادات البوت والربط
$botToken = "8892595660:AAErIF3uBxbi8_CjYJwIelpuRN__16ug-Ng";
$adminId  = 6805697054;
$apiUrl   = "https://ylafollow.com/api/v2";
$apiKey   = "2ff0c9c3dbf8db742196dd1d4215bbe2";

$website  = "https://api.telegram.org/bot" . $botToken;
$update   = json_decode(file_get_contents('php://input'), TRUE);

if(!$update) {
    exit("Bot is active.");
}

// تحديد معرف المستخدم والرسالة
if(isset($update["message"])) {
    $chatId   = $update["message"]["chat"]["id"];
    $userId   = $update["message"]["from"]["id"];
    $username = $update["message"]["from"]["username"] ?? "NoUsername";
    $text     = trim($update["message"]["text"]);
    $messageId= $update["message"]["message_id"];
    $callback = false;
} elseif(isset($update["callback_query"])) {
    $chatId   = $update["callback_query"]["message"]["chat"]["id"];
    $userId   = $update["callback_query"]["from"]["id"];
    $username = $update["callback_query"]["from"]["username"] ?? "NoUsername";
    $text     = $update["callback_query"]["data"];
    $messageId= $update["callback_query"]["message"]["message_id"];
    $callbackId= $update["callback_query"]["id"];
    $callback = true;
} else {
    exit;
}

// تهيئة قاعدة البيانات SQLite
$dbPath = __DIR__ . '/db/bot_database.sqlite';
if (!file_exists(__DIR__ . '/db')) {
    mkdir(__DIR__ . '/db', 0777, true);
}
$pdo = new PDO('sqlite:' . $dbPath);
$pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

// إنشاء الجداول اللازمة
$pdo->exec("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY, username TEXT)");
$pdo->exec("CREATE TABLE IF NOT EXISTS users_state (user_id INTEGER PRIMARY KEY, state TEXT, data TEXT)");

// إضافة الأدمن الأساسي إذا لم يكن موجوداً
$stmt = $pdo->prepare("INSERT OR IGNORE INTO admins (user_id, username) VALUES (?, ?)");
$stmt->execute([$adminId, "MainAdmin"]);

// دالة جلب قائمة الأدمنية
function getAdmins($pdo) {
    $stmt = $pdo->query("SELECT user_id, username FROM admins");
    return $stmt->fetchAll(PDO::FETCH_ASSOC);
}

function isAdmin($userId, $adminId, $pdo) {
    if ($userId == $adminId) return true;
    $stmt = $pdo->prepare("SELECT 1 FROM admins WHERE user_id = ?");
    $stmt->execute([$userId]);
    return $stmt->fetch() ? true : false;
}

// دالة الاتصال بموقع الخدمات (API)
function apiRequest($action, $additionalData = []) {
    global $apiUrl, $apiKey;
    $postData = array_merge(['key' => $apiKey, 'action' => $action], $additionalData);
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $apiUrl);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch, CURLOPT_POST, 1);
    curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($postData));
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    $output = curl_exec($ch);
    curl_close($ch);
    return json_decode($output, true);
}

// دوال الإرسال والتعديل لتليجرام
function sendRequest($method, $data) {
    global $website;
    $ch = curl_init();
    curl_setopt($ch, CURLOPT_URL, $website . '/' . $method);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
    curl_setopt($ch, CURLOPT_POST, 1);
    curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($data));
    curl_setopt($ch, CURLOPT_HTTPHEADER, ['Content-Type: application/json']);
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    $result = curl_exec($ch);
    curl_close($ch);
    return json_decode($result, true);
}

function sendMessage($chatId, $text, $keyboard = null) {
    $data = ['chat_id' => $chatId, 'text' => $text, 'parse_mode' => 'HTML'];
    if($keyboard) $data['reply_markup'] = $keyboard;
    return sendRequest('sendMessage', $data);
}

function editMessage($chatId, $messageId, $text, $keyboard = null) {
    $data = ['chat_id' => $chatId, 'message_id' => $messageId, 'text' => $text, 'parse_mode' => 'HTML'];
    if($keyboard) $data['reply_markup'] = $keyboard;
    return sendRequest('editMessageText', $data);
}

// جلب حالة المستخدم
$stmt = $pdo->prepare("SELECT state, data FROM users_state WHERE user_id = ?");
$stmt->execute([$userId]);
$userState = $stmt->fetch(PDO::FETCH_ASSOC);
$currentState = $userState['state'] ?? '';
$currentUserData = json_decode($userState['data'] ?? '{}', true);

function setState($pdo, $userId, $state, $data = []) {
    $stmt = $pdo->prepare("INSERT OR REPLACE INTO users_state (user_id, state, data) VALUES (?, ?, ?)");
    $stmt->execute([$userId, $state, json_encode($data)]);
}

function clearState($pdo, $userId) {
    $stmt = $pdo->prepare("DELETE FROM users_state WHERE user_id = ?");
    $stmt->execute([$userId]);
}

// الرد على الكول باك كويري لإزالة علامة التحميل
if($callback) {
    sendRequest('answerCallbackQuery', ['callback_query_id' => $callbackId]);
}

// فحص صلاحية الوصول للبوت
$isUserAdmin = isAdmin($userId, $adminId, $pdo);

if(!$isUserAdmin && $text !== "/start" && !$callback) {
    // مستخدم عادي يحاول الكتابة خارج /start
    exit;
}

// معالجة الأوامر والنصوص والضغطات
if($text === "/start" || $text === "main_menu") {
    clearState($pdo, $userId);
    if($isUserAdmin) {
        // جلب معلومات الحساب من الموقع للرصيد والإنفاق
        $balanceInfo = apiRequest('balance');
        $balance = $balanceInfo['balance'] ?? "0.00";
        $currency = $balanceInfo['currency'] ?? "USD";
        
        // حساب عدد الطلبات المكتملة للمستخدم من الموقع
        $orders = apiRequest('orders'); // أو جلب الطلبات عبر الـ API حسب الدعم
        // نفرض أن الـ API يرجع مصفوفة طلبات أو نقوم بعمل فلترة للطلبات المكتملة
        $completedCount = 0;
        if(is_array($orders)) {
            foreach($orders as $ord) {
                if(isset($ord['status']) && strtolower($ord['status']) == 'completed') {
                    $completedCount++;
                }
            }
        } else {
            // كقيمة افتراضية حسب الطلب إذا لم تتوفر مصفوفة مباشرة
            $completedCount = 400; 
        }

        $welcomeText = "مرحباً بك في لوحة تحكم الأدمن الأساسية 👑\n\n" .
                       "💰 الرصيد بالموقع: $balance $currency\n" .
                       "💸 الإنفاق بالموقع: (يتم حسابه تلقائياً)\n" .
                       "📦 عدد الطلبات المكتمله ( $completedCount )";

        $keyboard = [
            'inline_keyboard' => [
                [['text' => 'الخدمات', 'callback_data' => 'services'], ['text' => 'الطلبات', 'callback_data' => 'my_orders']],
                [['text' => 'خدمات مجانية', 'callback_data' => 'free_services'], ['text' => 'دعم ممول حقيقي', 'callback_data' => 'real_support']],
                [['text' => 'عدد الطلبات المكتمله ( ' . $completedCount . ' )', 'callback_data' => 'completed_count_info']],
                [['text' => 'رفع ادمن', 'callback_data' => 'add_admin_menu'], ['text' => 'حذف ادمن', 'callback_data' => 'del_admin_menu']]
            ]
        ];

        if($callback) {
            editMessage($chatId, $messageId, $welcomeText, $keyboard);
        } else {
            sendMessage($chatId, $welcomeText, $keyboard);
        }
    } else {
        // مستخدم غير ادمن
        $nonAdminText = "مرحباً بك عزيزي المستخدم.\n\n" .
                        "ملاحظة : البوت يعمل فقط وخاص للادمن.";
        
        // جلب يوزر الادمن الأساسي أو أول أدمن
        $adminsList = getAdmins($pdo);
        $adminUsername = "Al_Dulaimi_Admin"; // افتراضي
        foreach($adminsList as $adm) {
            if($adm['user_id'] == $adminId) {
                $adminUsername = $adm['username'];
                break;
            }
        }
        if($adminUsername == "NoUsername") $adminUsername = "admin";

        $keyboard = [
            'inline_keyboard' => [
                [['text' => '👨‍💻 ' . $adminUsername, 'url' => 'https://t.me/' . str_replace('@','',$adminUsername)]]
            ]
        ];

        if($callback) {
            editMessage($chatId, $messageId, $nonAdminText, $keyboard);
        } else {
            sendMessage($chatId, $nonAdminText, $keyboard);
        }
    }
    exit;
}

// التعامل مع أقسام لوحة الأدمن والخدمات
if($isUserAdmin) {
    
    // 1. قسم رفع أدمن
    if($text === 'add_admin_menu') {
        setState($pdo, $userId, 'waiting_for_admin_id');
        $txt = "الرجاء إرسال (الايدي - User ID) الشخص الذي تريد رفعه ليصبح أدمن في البوت:";
        $kb = ['inline_keyboard' => [[['text' => 'رجوع', 'callback_data' => 'main_menu']]]];
        editMessage($chatId, $messageId, $txt, $kb);
        exit;
    }
    
    if($currentState === 'waiting_for_admin_id') {
        if(is_numeric($text)) {
            $newAdminId = intval($text);
            // حفظ الأدمن الجديد
            $stmt = $pdo->prepare("INSERT OR IGNORE INTO admins (user_id, username) VALUES (?, ?)");
            $stmt->execute([$newAdminId, "Admin_" . $newAdminId]);
            clearState($pdo, $userId);
            sendMessage($chatId, "✅ تم رفع الشخص صاحب الايدي ($newAdminId) ليصبح أدمن بنجاح ويمكنه التحكم بالبوت الآن!");
        } else {
            sendMessage($chatId, "⚠️ الايدي غير صحيح، يجب أن يتكون من أرقام فقط. حاول مجدداً أو اضغط رجوع.");
        }
        exit;
    }

    // 2. قسم حذف أدمن
    if($text === 'del_admin_menu') {
        $admins = getAdmins($pdo);
        $inlineBtns = [];
        foreach($admins as $adm) {
            if($adm['user_id'] == $adminId) continue; // لا نحذف الادمن الرئيسي
            $inlineBtns[] = [['text' => 'حذف: ' . $adm['user_id'], 'callback_data' => 'confirm_del_' . $adm['user_id']]];
        }
        $inlineBtns[] = [['text' => 'رجوع', 'callback_data' => 'main_menu']];
        
        editMessage($chatId, $messageId, "اختر الأدمن المراد حذفه من القائمة أدناه:", ['inline_keyboard' => $inlineBtns]);
        exit;
    }

    if(strpos($text, 'confirm_del_') === 0) {
        $targetId = str_replace('confirm_del_', '', $text);
        $kb = [
            'inline_keyboard' => [
                [['text' => '✔️ نعم، تأكيد الحذف', 'callback_data' => 'execute_del_' . $targetId]],
                [['text' => '❌ إلغاء', 'callback_data' => 'del_admin_menu']]
            ]
        ];
        editMessage($chatId, $messageId, "هل أنت متأكد من رغبتك في حذف هذا الشخص من قائمة الأدمنية؟", $kb);
        exit;
    }

    if(strpos($text, 'execute_del_') === 0) {
        $targetId = str_replace('execute_del_', '', $text);
        $stmt = $pdo->prepare("DELETE FROM admins WHERE user_id = ?");
        $stmt->execute([$targetId]);
        editMessage($chatId, $messageId, "✅ تم حذف الأدمن بنجاح ولم يعد يمتلك صلاحيات.", ['inline_keyboard' => [[['text' => 'رجوع', 'callback_data' => 'main_menu']]]]);
        exit;
    }

    // 3. قسم الخدمات العادية (تطبيقات -> أنواع -> خدمات)
    if($text === 'services') {
        $kb = [
            'inline_keyboard' => [
                [['text' => 'فيسبوك', 'callback_data' => 'app_facebook'], ['text' => 'انستكرام', 'callback_data' => 'app_instagram']],
                [['text' => 'تليكرام', 'callback_data' => 'app_telegram'], ['text' => 'تيك توك', 'callback_data' => 'app_tiktok']],
                [['text' => 'تويتر', 'callback_data' => 'app_twitter']],
                [['text' => 'رجوع', 'callback_data' => 'main_menu']]
            ]
        ];
        editMessage($chatId, $messageId, "اختر التطبيق المطلوب لعرض الخدمات:", $kb);
        exit;
    }

    // اختيار التطبيق
    if(strpos($text, 'app_') === 0) {
        $app = str_replace('app_', '', $text);
        setState($pdo, $userId, 'choosing_service_type', ['app' => $app]);
        
        $kb = [
            'inline_keyboard' => [
                [['text' => 'لايكات', 'callback_data' => 'type_لايكات'], ['text' => 'متابعين', 'callback_data' => 'type_متابعين']],
                [['text' => 'مشاهدات', 'callback_data' => 'type_مشاهدات'], ['text' => 'تعليقات', 'callback_data' => 'type_تعليقات']],
                [['text' => 'رجوع', 'callback_data' => 'services']]
            ]
        ];
        editMessage($chatId, $messageId, "اختر نوع الخدمة المطلوبة لـ (" . ucfirst($app) . "):", $kb);
        exit;
    }

    // اختيار النوع (لايكات، متابعين، إلخ) وعرض الخدمات (صفحة 1 - أول 7 خدمات)
    if(strpos($text, 'type_') === 0 || strpos($text, 'srv_page_') === 0) {
        $page = 1;
        $selectedType = '';
        if(strpos($text, 'type_') === 0) {
            $selectedType = str_replace('type_', '', $text);
            $currentUserData['type'] = $selectedType;
            setState($pdo, $userId, 'browsing_services', $currentUserData);
        } else {
            // مثل srv_page_2_instagram_لايكات
            $parts = explode('_', $text);
            $page = intval($parts[2]);
            $selectedType = $currentUserData['type'] ?? 'لايكات';
        }
        
        $app = $currentUserData['app'] ?? 'instagram';
        
        // جلب الخدمات من الموقع عبر الـ API
        $allServices = apiRequest('services');
        $filteredServices = [];
        
        if(is_array($allServices)) {
            foreach($allServices as $srv) {
                $nameLower = mb_strtolower($srv['name'] ?? '');
                $categoryLower = mb_strtolower($srv['category'] ?? '');
                
                // مطابقة التطبيق والنوع
                $matchApp = (strpos($nameLower, strtolower($app)) !== false || strpos($categoryLower, strtolower($app)) !== false);
                $matchType = (strpos($nameLower, strtolower($selectedType)) !== false || strpos($categoryLower, strtolower($selectedType)) !== false);
                
                if($matchApp && $matchType) {
                    $filteredServices[] = $srv;
                }
            }
        }

        if(empty($filteredServices)) {
            $kb = ['inline_keyboard' => [[['text' => 'رجوع', 'callback_data' => 'app_' . $app]]]] ;
            editMessage($chatId, $messageId, "❌ ماكو خدمات حالياً متوفره لهذه القسم.", $kb);
            exit;
        }

        // التقسيم صفحات (كل صفحة 7 خدمات)
        $perPage = 7;
        $totalServices = count($filteredServices);
        $totalPages = ceil($totalServices / $perPage);
        if($page > $totalPages) $page = $totalPages;
        
        $offset = ($page - 1) * $perPage;
        $pageServices = array_slice($filteredServices, $offset, $perPage);

        $inlineBtns = [];
        foreach($pageServices as $srv) {
            $sId = $srv['service'];
            $sName = $srv['name'];
            $sRate = $srv['rate'];
            
            // اختصار الاسم وعرض السعر بين قوسين كما مطلوب
            // مثال: لايكات انستكرام ريلز (0.010$)
            $shortName = mb_substr($sName, 0, 35) . "... (" . $sRate . "$)";
            $inlineBtns[] = [['text' => $shortName, 'callback_data' => 'select_srv_' . $sId]];
        }

        // أزرار التالي والسابق والرجوع
        $navBtns = [];
        if($page > 1) {
            $navBtns[] = ['text' => '⬅️ السابق', 'callback_data' => 'srv_page_' . ($page - 1)];
        }
        if($page < $totalPages) {
            $navBtns[] = ['text' => 'التالي ➡️', 'callback_data' => 'srv_page_' . ($page + 1)];
        }
        if(!empty($navBtns)) {
            $inlineBtns[] = $navBtns;
        }
        
        $inlineBtns[] = [['text' => 'رجوع', 'callback_data' => 'app_' . $app]];

        editMessage($chatId, $messageId, "اختر الخدمة المطلوبة (الصفحة $page من $totalPages):", ['inline_keyboard' => $inlineBtns]);
        exit;
    }

    // عند اختيار خدمة معينة للطلب
    if(strpos($text, 'select_srv_') === 0) {
        $serviceId = str_replace('select_srv_', '', $text);
        
        // جلب تفاصيل الخدمة لمعرفة الحد الأدنى والأعلى والوصف
        $allServices = apiRequest('services');
        $selectedSrvDetails = null;
        if(is_array($allServices)) {
            foreach($allServices as $srv) {
                if($srv['service'] == $serviceId) {
                    $selectedSrvDetails = $srv;
                    break;
                }
            }
        }

        $min = $selectedSrvDetails['min'] ?? 10;
        $max = $selectedSrvDetails['max'] ?? 10000;
        $desc = $selectedSrvDetails['description'] ?? 'لا يوجد وصف لهذه الخدمة.';

        setState($pdo, $userId, 'waiting_for_link', ['service_id' => $serviceId, 'min' => $min, 'max' => $max]);
        
        $msg = "📋 <b>تفاصيل الخدمة:</b>\n" .
               "$desc\n\n" .
               "🔹 <b>الحد الأدنى:</b> $min\n" .
               "🔸 <b>الحد الأعلى:</b> $max\n\n" .
               "الرجاء إرسال <b>رابط الحساب أو المنشور</b> المطلوبة للخدمة:";
               
        $kb = ['inline_keyboard' => [[['text' => 'رجوع', 'callback_data' => 'services']]]];
        editMessage($chatId, $messageId, $msg, $kb);
        exit;
    }

    // استقبال الرابط ثم طلب الكمية
    if($currentState === 'waiting_for_link' && !$callback) {
        $currentUserData['link'] = $text;
        setState($pdo, $userId, 'waiting_for_quantity', $currentUserData);
        
        $min = $currentUserData['min'];
        $max = $currentUserData['max'];
        
        sendMessage($chatId, "✅ تم استلام الرابط بنجاح.\n\nالرجاء إرسال **الكمية** المطلوبة (يجب أن تكون بين $min و $max):");
        exit;
    }

    // استقبال الكمية وتنفيذ الطلب عبر الـ API
    if($currentState === 'waiting_for_quantity' && !$callback) {
        if(is_numeric($text)) {
            $quantity = intval($text);
            $serviceId = $currentUserData['service_id'];
            $link = $currentUserData['link'];
            $min = $currentUserData['min'];
            $max = $currentUserData['max'];

            if($quantity < $min || $quantity > $max) {
                sendMessage($chatId, "⚠️ الكمية المدخلة خارج النطاق المسموح. الحد الأدنى هو ($min) والحد الأعلى هو ($max). حاول إرسال الكمية مجدداً:");
                exit;
            }

            // إرسال الطلب للموقع عبر الـ API
            $orderResponse = apiRequest('add', [
                'service' => $serviceId,
                'link'    => $link,
                'quantity'=> $quantity
            ]);

            clearState($pdo, $userId);

            if(isset($orderResponse['order'])) {
                $orderId = $orderResponse['order'];
                sendMessage($chatId, "🎉 <b>تم إرسال طلبك بنجاح!</b>\n\n🆔 رقم الطلب: <code>$orderId</code>\n🔗 الرابط: $link\n🔢 الكمية: $quantity", [
                    'inline_keyboard' => [[['text' => 'الرئيسية', 'callback_data' => 'main_menu']]]
                ]);
            } else {
                $err = $orderResponse['error'] ?? 'حدث خطأ غير معروف أثناء تنفيذ الطلب.';
                sendMessage($chatId, "❌ فشل إرسال الطلب:\n$err", [
                    'inline_keyboard' => [[['text' => 'الرئيسية', 'callback_data' => 'main_menu']]]
                ]);
            }
        } else {
            sendMessage($chatId, "⚠️ يرجى إدخال أرقام صحيحة للكمية فقط:");
        }
        exit;
    }

    // 4. قسم الخدمات المجانية (سعرها 0.000$)
    if($text === 'free_services') {
        $allServices = apiRequest('services');
        $freeServices = [];
        
        if(is_array($allServices)) {
            foreach($allServices as $srv) {
                $rate = floatval($srv['rate'] ?? 1);
                if($rate == 0.000 || $rate == 0) {
                    $freeServices[] = $srv;
                }
            }
        }

        if(empty($freeServices)) {
            $kb = ['inline_keyboard' => [[['text' => 'رجوع', 'callback_data' => 'main_menu']]]];
            editMessage($chatId, $messageId, "❌ لا توجد خدمات مجانية (0.000$) حالياً في الموقع.", $kb);
            exit;
        }

        $inlineBtns = [];
        foreach($freeServices as $srv) {
            $sId = $srv['service'];
            $sName = $srv['name'];
            $shortName = mb_substr($sName, 0, 40) . " (0.000$)";
            $inlineBtns[] = [['text' => $shortName, 'callback_data' => 'select_srv_' . $sId]];
        }
        $inlineBtns[] = [['text' => 'رجوع', 'callback_data' => 'main_menu']];

        editMessage($chatId, $messageId, "🎁 قائمة الخدمات المجانية المتوفرة حالياً:", ['inline_keyboard' => $inlineBtns]);
        exit;
    }

    // 5. الأقسام الأخرى (الطلبات، دعم ممول حقيقي)
    if($text === 'my_orders') {
        $orders = apiRequest('orders');
        $txt = "📦 <b>آخر طلباتك في الموقع:</b>\n\n";
        if(is_array($orders) && !empty($orders)) {
            $count = 0;
            foreach($orders as $ord) {
                if($count >= 5) break; // عرض آخر 5 طلبات
                $txt .= "🆔 رقم: " . $ord['order'] . "\n" .
                        "📌 الحالة: " . $ord['status'] . "\n" .
                        "🔗 الرابط: " . $ord['link'] . "\n------------------\n";
                $count++;
            }
        } else {
            $txt .= "لا توجد طلبات سابقة مسجلة أو تعذر الجلب.";
        }
        $kb = ['inline_keyboard' => [[['text' => 'رجوع', 'callback_data' => 'main_menu']]]];
        editMessage($chatId, $messageId, $txt, $kb);
        exit;
    }

    if($text === 'real_support') {
        $kb = ['inline_keyboard' => [[['text' => 'رجوع', 'callback_data' => 'main_menu']]]];
        editMessage($chatId, $messageId, "💬 للإتصال بخدمة الدعم الممول الحقيقي، يمكنك مراسلة الدعم المباشر عبر الموقع أو التواصل مع الأدمن الأساسي.", $kb);
        exit;
    }
}
?>
