const ROLE_NIGHT_DATA = {
  doppelganger: {
    name: '도플갱어',
    image: '/roles/doppelganger.png',
    announce: '도플갱어는 깨어나세요.',
    action: '다른 플레이어 1명의 카드를 확인하세요.\n그 역할이 됩니다.',
  },
  werewolf: {
    name: '늑대인간',
    image: '/roles/werewolf.png',
    announce: '늑대인간은 깨어나세요.',
    action: '서로를 확인하고 다시 눈을 감으세요.',
  },
  minion: {
    name: '하수인',
    image: '/roles/minion.png',
    announce: '하수인은 깨어나세요.',
    action: '늑대인간들은 엄지를 들어올려\n자신을 알려주세요.',
  },
  mason: {
    name: '프리메이슨',
    image: '/roles/mason.png',
    announce: '프리메이슨은 깨어나세요.',
    action: '서로를 확인하고 다시 눈을 감으세요.',
  },
  seer: {
    name: '예언자',
    image: '/roles/seer.png',
    announce: '예언자는 깨어나세요.',
    action: '다른 플레이어 1명 또는\n중앙 카드 2장을 확인할 수 있습니다.',
  },
  robber: {
    name: '강도',
    image: '/roles/robber.png',
    announce: '강도는 깨어나세요.',
    action: '다른 플레이어 1명의 카드와\n자신의 카드를 교환할 수 있습니다.',
  },
  troublemaker: {
    name: '말썽쟁이',
    image: '/roles/troublemaker.png',
    announce: '말썽쟁이는 깨어나세요.',
    action: '자신을 제외한 두 플레이어의\n카드를 서로 교환하세요.',
  },
  drunk: {
    name: '주정뱅이',
    image: '/roles/drunk.png',
    announce: '주정뱅이는 깨어나세요.',
    action: '중앙 카드 1장을 가져와\n자신의 카드와 교환하세요.\n새 카드는 볼 수 없습니다.',
  },
  insomniac: {
    name: '불면증환자',
    image: '/roles/insomniac.png',
    announce: '불면증환자는 깨어나세요.',
    action: '자신의 카드를 확인하세요.',
  },
}

export default function NightRoleAnnounce({ roleId, onComplete }) {
  const role = ROLE_NIGHT_DATA[roleId]
  if (!role) return null

  return (
    <div onClick={onComplete} style={styles.page}>
      <div style={styles.inner}>
        <div style={styles.roleName}>{role.name}</div>

        <div style={styles.imageBox}>
          <img src={role.image} alt={role.name} style={styles.image} />
        </div>

        <div style={styles.textBlock}>
          <p style={styles.announceText}>{role.announce}</p>
          <p style={styles.actionText}>{role.action}</p>
        </div>
      </div>
    </div>
  )
}

const styles = {
  page: {
    minHeight: '100vh',
    background: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: "'Segoe UI', 'Apple SD Gothic Neo', sans-serif",
    cursor: 'pointer',
    userSelect: 'none',
  },
  inner: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 20,
    marginTop: '-60px',
  },
  roleName: {
    fontSize: 18,
    fontWeight: 600,
    color: '#111',
  },
  imageBox: {
    width: 120,
    height: 150,
    borderRadius: 10,
    overflow: 'hidden',
    background: '#e4e4e4',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  image: {
    width: '100%',
    height: '100%',
    objectFit: 'contain',
  },
  textBlock: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 6,
  },
  announceText: {
    margin: 0,
    fontSize: 16,
    fontWeight: 500,
    color: '#111',
    textAlign: 'center',
  },
  actionText: {
    margin: 0,
    fontSize: 14,
    color: '#444',
    textAlign: 'center',
    lineHeight: 1.7,
    whiteSpace: 'pre-line',
  },
}
